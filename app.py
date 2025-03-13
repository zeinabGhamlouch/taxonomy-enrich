from flask import Flask, request, jsonify, send_file, render_template
import json
from io import BytesIO
from typing import Any, List, Dict

app = Flask(__name__)

# Your analyze_taxonomy function (unchanged)
def analyze_taxonomy(json_taxonomy):
    def count_nodes(node):
        return 1 + sum(count_nodes(child) for child in node.get("children", []))

    def max_depth(node):
        if not node.get("children"):
            return 1
        return 1 + max(max_depth(child) for child in node["children"])

    def branching_factor(node):
        if not node.get("children"):
            return 0, 0
        total_children = len(node["children"])
        total_parents = 1
        for child in node["children"]:
            child_children, child_parents = branching_factor(child)
            total_children += child_children
            total_parents += child_parents
        return total_children, total_parents

    root_name = json_taxonomy.get("name", "Unknown Root")
    total_nodes = count_nodes(json_taxonomy)
    depth = max_depth(json_taxonomy)
    total_children, total_parents = branching_factor(json_taxonomy)
    avg_branching_factor = total_children / total_parents if total_parents else 0

    return {
        "Root Name": root_name,
        "Total Nodes": total_nodes,
        "Max Depth": depth,
        "Average Branching Factor": avg_branching_factor
    }

# Merging helper functions (updated)
def load_json(file_path: str) -> Any:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in file {file_path}: {e}")

def save_json(data: Any, file_path: str) -> None:
    def reorder_keys(obj):
        if isinstance(obj, dict):
            keys = sorted(obj.keys(), key=lambda k: (k != "name", k))
            return {key: reorder_keys(obj[key]) for key in keys}
        elif isinstance(obj, list):
            return [reorder_keys(item) for item in obj]
        return obj

    reordered_data = reorder_keys(data)
    with open(file_path, 'w') as file:
        json.dump(reordered_data, file, indent=4)

def deduplicate_list(items: List[Dict]) -> List[Dict]:
    seen = set()
    unique_items = []
    for item in items:
        item_key = json.dumps(item, sort_keys=True)
        if item_key not in seen:
            seen.add(item_key)
            unique_items.append(item)
    return unique_items

def merge_children(children1: List[Dict], children2: List[Dict]) -> List[Dict]:
    merged = {child["name"]: child for child in children1}
    for child in children2:
        if child["name"] in merged:
            merged[child["name"]] = union_merge_json(merged[child["name"]], child)
        else:
            merged[child["name"]] = child
    return list(merged.values())

def union_merge_json(json1: Any, json2: Any) -> Any:
    if isinstance(json1, dict) and isinstance(json2, dict):
        merged = {}
        for key in set(json1.keys()).union(json2.keys()):
            if key == "children":
                merged[key] = merge_children(json1.get(key, []), json2.get(key, []))
            else:
                merged[key] = union_merge_json(json1.get(key), json2.get(key))
        return merged
    elif isinstance(json1, list) and isinstance(json2, list):
        return deduplicate_list(json1 + json2)
    else:
        return json1
    
def merge_trees(tree1: Dict, tree2: Dict) -> Dict:
    # Ensure root is at the top and merge the rest
    root1 = tree1.get("name")
    root2 = tree2.get("name")
    
    if root1 != root2:
        merged = {
            "name": f"merged_{root1}_{root2}",  # Combine roots' names for clarity
            "children": merge_children([tree1], [tree2])
        }
    else:
        merged = union_merge_json(tree1, tree2)
        
    return merged

# Serve index.html when the root URL is accessed
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze_taxonomy', methods=['POST'])
def analyze_taxonomy_endpoint():
    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file provided'}), 400

    try:
        taxonomy_data = json.load(file)
        analysis_result = analyze_taxonomy(taxonomy_data)
        return jsonify({
            "analysis": analysis_result,
            "taxonomy": taxonomy_data  # Returning the full taxonomy for visualization
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@app.route('/merge_taxonomies', methods=['POST'])
def merge_taxonomies():
    try:
        # Get both taxonomy files from the form data
        taxonomy1_file = request.files['taxonomy1']
        taxonomy2_file = request.files['taxonomy2']
        
        if not taxonomy1_file or not taxonomy2_file:
            return jsonify({'error': 'Please upload both taxonomy files'}), 400

        # Load the content of the JSON files
        taxonomy1 = json.load(taxonomy1_file)
        taxonomy2 = json.load(taxonomy2_file)
        
        # Merge the two taxonomies using the existing merge function
        merged_taxonomy = merge_trees(taxonomy1, taxonomy2)
        
        # Save the merged result to a BytesIO object to simulate a file for download
        merged_json = json.dumps(merged_taxonomy, indent=4)
        merged_file = BytesIO(merged_json.encode('utf-8'))
        merged_file.seek(0)  # Go to the start of the BytesIO buffer
        
        # Return the merged JSON file as a downloadable response
        return send_file(
            merged_file,
            as_attachment=True,
            download_name="merged_taxonomy.json",
            mimetype="application/json"
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
