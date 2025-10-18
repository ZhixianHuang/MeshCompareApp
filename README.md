Some mesh might be skipped (identified as correct mesh) use script -f /tmp/terminal_output.log   tail -f /tmp/terminal_output.log | ./monitor.sh command to detect those mesh  
run script -f /tmp/terminal_output.log before run compare_mesh_app/compare_mesh.sh  
run tail -f /tmp/terminal_output.log | ./monitor.sh under results_missing_id in another terminal  
monitor.sh will record all the skipped id in window and compare_mesh.sh will delete all the recorded ids from processed list before visualizing the mesh  

the project is ready to used but still need to be maintained, currently all paths are designed for my use.
