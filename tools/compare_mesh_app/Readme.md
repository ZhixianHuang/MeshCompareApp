# Mesh Viewer Application

A Python-based 3D mesh visualization tool specifically designed for comparing reconstructed 3D models (MVS meshes) with their corresponding ground truth meshes. This tool streamlines the process of visually inspecting large batches of 3D meshes to identify and document quality issues.

## Features

- **Dual Mesh Visualization**: Simultaneously view MVS reconstructed meshes alongside ground truth meshes
- **Intuitive Navigation**: Simple keyboard controls for navigating through mesh collections
- **Quality Assessment**: Quickly mark meshes as satisfactory or unsatisfactory
- **Progress Tracking**: Automatically saves progress and quality assessment results
- **Session Recovery**: Resume mesh review sessions from where you left off
- **Automated Error Detection**: Identifies common mesh issues like missing files, empty meshes, etc.
- **Statistical Summary**: Provides a summary of mesh quality statistics at the end of review sessions

## Prerequisites

- Python 3.x
- Required Python packages:
  - numpy == 1.26
  - open3d
  - tkinter (usually comes with Python)

## Installation

1. Clone this repository or download the source code
2. Install the required dependencies:

```bash
pip install numpy open3d
```

## Usage

Run the application from the command line with the following parameters:

```bash
python mesh_viewer.py --category CATEGORY --side SIDE [--test]
```

### Required Arguments

- `--category`: The model category to inspect (airplane, cabinet, car, chair, lamp, sofa, table, watercraft)
- `--side`: View perspective (left or right)

### Optional Arguments

- `--test`: Force restart a new checking session (as if meshes have been updated)

## Controls

- **Space**: View next mesh
- **Left Arrow**: Return to previous mesh
- **D key**: Mark current mesh as unsatisfactory and move to next mesh
- **Q or ESC**: Exit the application

## Workspace Organization

The application expects the following directory structure:

```
/path/to/ShapeNet/norm_mesh_dir_v1/
└── CATEGORY_ID/
    └── OBJECT_ID/
        └── pc_norm.obj (Ground truth mesh)

/path/to/mvs_shape/
└── mvs_SIDE_CATEGORY/
    └── OBJECT_ID/
        └── Tile_00000_mesh.ply (MVS reconstructed mesh)
        └── Tile_00000_pcloud_poisson.ply (Poisson reconstructed mesh - optional)
```

## Output Files

The application creates and maintains the following files in the `./results` directory:

1. **Checkpoint File**: 
   - Format: `mesh_review_checkpoint_mvs_SIDE_CATEGORY_TIMESTAMP.txt`
   - Purpose: Records processed mesh IDs to enable session resumption

2. **Results File**:
   - Format: `mesh_review_results_mvs_SIDE_CATEGORY_TIMESTAMP.csv`
   - Purpose: Records problematic meshes with categorized issues

## Error Categories

The application identifies and categorizes the following types of issues:

- **MVS not exist**: MVS reconstructed mesh file is missing
- **MVS mesh invalid**: MVS mesh has insufficient vertices or faces
- **Load MVS mesh failed**: Error occurred while loading the MVS mesh
- **GT mesh not exist**: Ground truth mesh file is missing
- **GT mesh invalid**: Ground truth mesh has insufficient vertices or faces
- **Load GT mesh failed**: Error occurred while loading the ground truth mesh
- **Mesh unsatisfactory**: User-marked quality issues (using 'D' key)

## Implementation Details

- Meshes are automatically normalized and transformed for consistent visualization
- Different mesh categories have specialized viewing angles for optimal inspection
- The application includes a debouncing mechanism to prevent accidental double key presses
- Session data is automatically consolidated from previous runs
- Meshes with detected issues are automatically skipped during review

## Customization

You may need to adjust the hardcoded paths in the script to match your directory structure:

```python
self.gt_dir = os.path.join("/path/to/ShapeNet/norm_mesh_dir_v1", self.category_id)
self.recon_dir = os.path.join("/path/to/mvs_shape", f"mvs_{self.object_side}_{self.category_name}")
```

## Troubleshooting

- If the application fails to display meshes, verify that the paths are correctly configured
- If the Open3D window doesn't respond to keyboard input, click inside the window first to ensure it has focus
- For visualization issues, check that you have the correct version of Open3D (requires Numpy<2.0, tested on Numpy==1.26)

## License

[Insert license information here]

## Acknowledgments

[Optional section for credits, inspiration, etc.]