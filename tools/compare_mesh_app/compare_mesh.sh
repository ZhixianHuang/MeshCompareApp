#!/bin/bash


CATEGORY="lamp"
SIDE="left_front"

python /home/huangzhixian/mesh3d/SDFusion/results_missing_id/delete_missing_ids.py --category "$CATEGORY" --side "$SIDE"

# "left" = "right_front"
# "right" = "right_back"


### enforce a new round := meshes has been updated, add --test to the following command-line
python /home/huangzhixian/mesh3d/SDFusion/tools/compare_mesh_app/compare_mesh.py --category "$CATEGORY" --side "$SIDE" --notexture  # --test

### Very Important 
# update 4 + rotation around y axis 90 degrees
# including right front airplane, cabinet, chair, lamp, sofa, table, watercraft 
# including right back airplane, cabinet, chair, lamp, sofa, table, watercraft 

### finished 
# left_back: cabinet car watercraft lamp
# left_front: airplane(0,1 missing) cabinet(0 missing) car watercraft  lamp
