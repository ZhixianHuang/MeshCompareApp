import os
import csv
import glob
import numpy as np
import open3d as o3d
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
import argparse


class MeshViewerApp:
    def __init__(self, category, category_id, object_side, test, notext):
        # Path definition
        self.category_name = category
        self.category_id = category_id
        self.object_side = object_side
        self.notext = notext
        self.gt_dir = os.path.join(
            "/home/huangzhixian/mesh3d/SDFusion/data/ShapeNet/norm_mesh_dir_v1", self.category_id
        )
        
        self.recon_dir = os.path.join(
            "/home/huangzhixian/mesh3d/SDFusion/data/mvs_shape",
            f"mvs_{self.object_side}_{self.category_name}",
        )
        self.save_dir = f"mvs_{self.object_side}_{self.category_name}"

        self.save_root = f"/home/huangzhixian/mesh3d/SDFusion/results"
        os.makedirs(self.save_root, exist_ok=True)

        # Get all the to be checked object ids
        # all object ids
        self.all_object_ids = sorted(os.listdir(self.gt_dir))

        self.current_index = 0

        # Initialize counters for different error types
        self.gt_not_exist = 0
        self.mvs_not_exist = 0
        self.invalid_mvs = 0
        self.load_mvs_failure = 0
        self.invalid_gt = 0
        self.load_gt_failure = 0
        self.check_succeed_mesh = 0

        # Add key anti-repeat mechanism
        self.last_key_time = 0  # Last key press time
        self.key_cooldown = 0.5  # Key cooldown time (seconds)

        self.failure_ids = self.load_prev_id()

        # Create a CSV file that records all failed object_ids and their reasons
        self.results_file = os.path.join(
            self.save_root, f"mesh_review_results_{self.save_dir}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        # Create the results file with proper headers
        with open(self.results_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["category_id", "object_id", "reason"])

        # Initialize the dictionary to store previous records
        self.previous_records = {}

        # Load any existing results from previous sessions
        self.load_previous_results()

        # Create a checkpoint file to record processed meshes for resuming later
        self.checkpoint_file = os.path.join(
            self.save_root, f"mesh_review_checkpoint_{self.save_dir}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        # Check if there's a checkpoint file to resume from
        self.processed_ids = self.load_checkpoint()

        checkpoint_missing = len(self.processed_ids) == 0
        if checkpoint_missing:
            if len(self.failure_ids) == 0:
                print("No records of Checkpoint file nor Results csv file, a restart from scratch is necessary")
                # process all files
                self.object_ids = sorted(self.all_object_ids)
                self.processed_ids = []
            else:
                print("Results csv file recorded, Checkpoint missing, re-create a Checkpoint file")
                self.processed_ids = list(set(self.all_object_ids) - set(self.failure_ids))
                self.object_ids = sorted(self.failure_ids)
                self.init_checkpoint()
        else:
            # check crush, operation is recover from the checkpoint, where self.restart = False
            # check finish, opertion is (after maunal update the problematic meshes) igonored the qualified meshes,
            # and maunal check the updated meshes
            # There is a bug here, processed_ids is one less than all_object_ids even after all processing is done
            # Guess is the last object hasn't been record if it is correct
            # If the last one is problematic, guess it can be recorded correctly leads to the equal of these two amt
            if len(self.all_object_ids) == len(self.processed_ids) + 1 or len(self.all_object_ids) == len(self.processed_ids):
                self.restart = True
            else:
                self.restart = False

            # a new round of test can be enforced restarted
            # 'self.restart = True` is used for debugging purposes:
            # It forces a new review round even if no new meshes are added.
            # This allows rechecking certain meshes (manually marked as invalid)
            # to observe how the log and result files are updated.

            self.restart = self.restart or test

            if self.restart:
                self.processed_ids = list(set(self.processed_ids) - set(self.failure_ids))
                # remove would update the ckpt file by removing the failure ids
                self.update_checkpoint(add=False, remove=True)

            # if it's not the start of a new round means it's crushed down during the check process
            # no need to clear the failure ids again, it has been cleared at the beginning of the round
            # checked ids before crush have been recorded to the ckpt
            self.object_ids = sorted(list(set(self.all_object_ids) - set(self.processed_ids)))

        # Initialize Tkinter root for dialogs
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the main window
        self.root.title("Mesh Viewer")

        # Initialize the Open3D window
        self.vis = o3d.visualization.VisualizerWithKeyCallback()
        self.vis.create_window("Mesh Comparison Viewer", width=3000, height=2250)

        # Modification
        self.vis.get_render_option().mesh_show_back_face = True

        # Register key callbacks with debouncing mechanism
        self.vis.register_key_callback(32, self.debounce_key(self.next_mesh))  # Space (32)
        self.vis.register_key_callback(263, self.debounce_key(self.prev_mesh))  # Left-Arrow (263)
        self.vis.register_key_callback(100, self.debounce_key(self.handle_d_key))  # 'd' key (100) for marking unsatisfactory
        self.vis.register_key_callback(68, self.debounce_key(self.handle_d_key))  # 'D' key (68) for marking unsatisfactory

        # Add a general key callback to print key codes for debugging
        self.vis.register_key_callback(-1, self.debounce_key(self.print_key_code, log_only=True))  # -1 means catch all keys

        # Load first mesh
        self.load_current_meshes()

        # Start visualization loop
        self.run()

    def load_prev_id(self):
        prev_result = None
        prev_results = os.listdir(self.save_root)
        for result in prev_results:
            if "results" in result and self.save_dir in result:
                prev_result = result
                break

        if prev_result is None:
            return []
        else:
            with open(os.path.join(self.save_root, prev_result), "r", newline="") as f:
                reader = csv.reader(f)
                # skip the header
                header = next(reader, None)
                ids = sorted(item[1] for item in list(reader))
                # print(ids)
            return ids

    def load_previous_results(self):
        """Load all previous results files for the same category and merge them"""
        self.previous_records = {}  # Use a dict to store record with reason
        # Find all previous results files for this category
        previous_files = glob.glob(os.path.join(self.save_root, f"mesh_review_results_{self.save_dir}_*.csv"))

        if previous_files:
            latest_result = min(previous_files, key=os.path.getctime)
            try:
                with open(latest_result, "r", newline="") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)  # Skip header row but save it to check if it exists

                    # Check if file has content (including header)
                    if header is None:
                        print(f"Warning: Previous results file {latest_result} is empty or has no header")

                    # Check if the header is as expected
                    if header != ["category_id", "object_id", "reason"]:
                        print(f"Warning: Previous results file {latest_result} has unexpected header: {header}")

                    for row in reader:
                        if len(row) >= 3:  # Ensure we have category_id, object_id, and reason
                            # Store category_id and object_id as key, reason as value
                            record_key = (row[0], row[1])
                            self.previous_records[record_key] = row[2]

                            # Update counters based on reason field
                            reason = row[2]
                            if reason == "MVS not exist":
                                self.mvs_not_exist += 1
                            elif reason == "MVS mesh invalid":
                                self.invalid_mvs += 1
                            elif reason == "Load MVS mesh failed":
                                self.load_mvs_failure += 1
                            elif reason == "GT mesh not exist":
                                self.gt_not_exist += 1
                            elif reason == "GT mesh invalid":
                                self.invalid_gt += 1
                            elif reason == "Load GT mesh failed":
                                self.load_gt_failure += 1

                print(f"Loaded {len(self.previous_records)} records from previous results file: {latest_result}")
            except Exception as e:
                print(f"Error loading previous results from {latest_result}: {e}")

            # Copy all previous records to the new results file
            with open(self.results_file, "w", newline="") as f:  # Use 'w' mode to create a new file
                writer = csv.writer(f)
                writer.writerow(["category_id", "object_id", "reason"])  # Write header
                for (category_id, object_id), reason in self.previous_records.items():
                    writer.writerow([category_id, object_id, reason])

            # DO NOT convert previous_records to a set - keep it as a dictionary for later use

            if previous_files:
                # Delete previous files after successful migration
                for file_path in previous_files:
                    if file_path == self.results_file:
                        continue
                    try:
                        os.remove(file_path)
                        print(f"Deleted previous results file: {file_path}")
                    except Exception as e:
                        print(f"Error deleting file {file_path}: {e}")

    def load_checkpoint(self):
        """Look for the most recent checkpoint file and resume from there if found"""
        checkpoint_files = glob.glob(os.path.join(self.save_root, f"mesh_review_checkpoint_{self.save_dir}*.txt"))

        # if there's a ckpt file, copy all the existing ids to the new ckpt file and return them
        if checkpoint_files:
            # Get the most recent checkpoint file
            latest_checkpoint = max(checkpoint_files, key=os.path.getctime)

            try:
                with open(latest_checkpoint, "r") as f:
                    processed_ids = f.read().splitlines()

                if processed_ids:
                    # last_processed_id = processed_ids[-1]
                    # if last_processed_id in self.object_ids:
                    #     resume_index = self.object_ids.index(last_processed_id)
                    #     # Start from the next mesh after the last processed one
                    #     self.current_index = min(resume_index + 1, len(self.object_ids) - 1)
                    #     print(f"Resuming from mesh {self.current_index + 1}/{len(self.object_ids)}: {self.object_ids[self.current_index]}")

                    # Copy processed IDs to our new checkpoint file
                    with open(self.checkpoint_file, "w") as new_f:
                        for pid in processed_ids:
                            new_f.write(f"{pid}\n")
            except Exception as e:
                print(f"Error loading checkpoint: {e}")

        if checkpoint_files:
            # After loading checkpoint, delete all previous checkpoint files
            for file_path in checkpoint_files:
                try:
                    os.remove(file_path)
                    print(f"Deleted previous checkpoint file: {file_path}")
                except Exception as e:
                    print(f"Error deleting checkpoint file {file_path}: {e}")
            if processed_ids:
                return processed_ids
            else:
                return []
        else:
            return []

    def init_checkpoint(self):
        with open(self.checkpoint_file, "w") as f:
            for id in self.processed_ids:
                f.write(f"{id}\n")

    def update_checkpoint(self, add=True, remove=False):
        """Update the checkpoint file with the current object ID"""
        if add:
            with open(self.checkpoint_file, "a") as f:
                f.write(f"{self.object_ids[self.current_index]}\n")
        else:
            if not remove:
                # Remove the last line (used when going back)
                try:
                    with open(self.checkpoint_file, "r") as f:
                        lines = f.readlines()

                    if lines:
                        with open(self.checkpoint_file, "w") as f:
                            f.writelines(lines[:-1])
                except Exception as e:
                    print(f"Error updating checkpoint: {e}")

        if remove:
            with open(self.checkpoint_file, "w") as f:
                for id in self.processed_ids:
                    f.write(f"{id}\n")

    def update_reults(self):
        """Update the result file with the current object ID"""
        new_rows = []
        obj_id = self.object_ids[self.current_index]
        category_id = self.category_id

        new_failure_ids = []
        if obj_id in self.failure_ids:
            # filter the current id
            with open(self.results_file, "r", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)  # skip header
                for row in reader:
                    if not (len(row) >= 2 and row[0] == category_id and row[1] == obj_id):
                        new_rows.append(row)
                        new_failure_ids.append(row[1])
                    else:
                        print(f"Detected in current results file {category_id}/{obj_id} {row[2]}")
                        print('New mesh satisfied')

            # write the ids besides the filtered one
            with open(self.results_file, "w", newline="") as f:
                writer = csv.writer(f)
                if header:
                    writer.writerow(header)
                writer.writerows(new_rows)
        if len(new_failure_ids) != 0:
            self.failure_ids = new_failure_ids
        # self.failure_ids = new_failure_ids if len(new_failure_ids) != 0 else 

    def normalize_mesh(self, mesh):
        """Normalize mesh to fit within a unit sphere"""
        vertices = np.asarray(mesh.vertices)
        # Find the maximum distance from the origin
        max_distance = np.max(np.linalg.norm(vertices, axis=1))

        # Normalize all vertices
        if max_distance > 0:
            normalized_vertices = vertices / max_distance
            mesh.vertices = o3d.utility.Vector3dVector(normalized_vertices)

        return mesh

    def color_mesh(self, mesh, color="light blue"):
        """Assign a color for the mesh"""
        color_dict = {
            "light blue": [0.7, 0.7, 1.0],  # 淡蓝色
            "sky blue": [0.2, 0.6, 1.0],  # 天蓝色
            "red": [1.0, 0.3, 0.3],  # 预测 红色
            "green": [0.3, 0.9, 0.3],  # 辅助用绿色
            "yellow": [1.0, 1.0, 0.0],  # 错误区域 高亮黄色
            "cyan": [0.0, 1.0, 0.6],  # 青绿色
            "purple": [0.6, 0.2, 0.8],  # 紫色
            "orange": [1.0, 0.5, 0.0],  # 橙色
            "gray": [0.5, 0.5, 0.5],  # 中灰色
            "white": [1.0, 1.0, 1.0],  # 白色
            "black": [0.0, 0.0, 0.0],  # 黑色
        }

        # Load vertices and faces of current mesh
        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)

        # Create a new colored version of the input mesh
        mesh_colored = o3d.geometry.TriangleMesh()
        mesh_colored.vertices = o3d.utility.Vector3dVector(vertices)
        mesh_colored.triangles = o3d.utility.Vector3iVector(triangles)
        mesh_colored.compute_vertex_normals()

        # Apply color
        vertex_colors = np.ones((len(vertices), 3)) * np.array(color_dict[color])
        mesh_colored.vertex_colors = o3d.utility.Vector3dVector(vertex_colors)

        return mesh_colored

    def modify_mesh(self, mesh, centralize=True, translation=[0, 0, 0], rotation_y_degrees=0):
        """
        Normalize mesh to fit within a unit sphere and apply transformations

        Args:
            mesh: The mesh to normalize
            center_to_origin: Whether to center the mesh at origin (0,0,0)
            translation: [x, y, z] translation to apply after normalization
            rotation_y_degrees: Rotation angle in degrees around Y axis
        """
        vertices = np.asarray(mesh.vertices)

        # shift the mesh to the origin by the mean of all vertices
        if centralize:
            center = np.mean(vertices, axis=0)
            vertices = vertices - center
        # Apply Y-axis rotation if requested
        if rotation_y_degrees is not False:
            # Convert to radians
            theta = np.radians(rotation_y_degrees)

            # Rotation matrix around Y axis
            rot_y = np.array([[np.cos(theta), 0, np.sin(theta)], [0, 1, 0], [-np.sin(theta), 0, np.cos(theta)]])

            # Apply rotation
            vertices = np.matmul(vertices, rot_y.T)

        # Apply translation if requested
        if translation is not False:
            vertices += np.array(translation)

        mesh.vertices = o3d.utility.Vector3dVector(vertices)

        return mesh

    def show_mesh_check_results(self):
        # Force lift the root window to top
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)

        result = messagebox.showinfo(
            "Info",
            f"""Check mesh finished, {self.current_index+1} mesh(es) checked, \n
                            {self.mvs_not_exist} mvs mesh(es) have no reconstructed MVS mesh, \n
                            {self.invalid_mvs} mvs mesh(es) have not enough vertices and are recognized as invalid, \n
                            {self.load_mvs_failure} mvs mesh(es) cannot be loaded correctly \n
                         
                            {self.gt_not_exist} gt mesh(es) have no normalized ground truth, \n
                            {self.invalid_gt} gt mesh(es) have not enough vertices and are recognized as invalid \n
                            {self.load_gt_failure} gt mesh(es) cannot be loaded correctly \n
                            {self.check_succeed_mesh} mvs mesh(es) have been reconstructed successfully
                            """,
        )

        self.root.attributes("-topmost", False)
        self.root.withdraw()
        return result

    def load_current_meshes(self):
        if not self.object_ids:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            messagebox.showerror("Error", "There are no available meshes. GT mesh directory might be wrong")
            self.root.attributes("-topmost", False)
            self.root.withdraw()
            return

        # Clear previous geometries
        self.vis.clear_geometries()

        obj_id = self.object_ids[self.current_index]
        category_id = self.category_id

        # Check if the reconstructed mesh exists
        recon_path = os.path.join(self.recon_dir, obj_id, "Tile_00000_mesh.ply")
        poisson_recon_path = os.path.join(self.recon_dir, obj_id, "Tile_00000_pcloud_poisson.ply")
        if os.path.exists(poisson_recon_path):
            recon_path = poisson_recon_path

        # MVS does not exist
        if not os.path.exists(recon_path):
            print(f"MVS reconstructed mesh doesn't exist: {recon_path}")
            self.record_invalid_mesh(category_id, obj_id, "MVS not exist")
            self.failure_ids.append(obj_id)
            self.mvs_not_exist += 1

            # Update checkpoint
            self.update_checkpoint()

            # Update the window title to indicate the mesh doesn't exist
            window_title = f"[MVS NOT EXIST] {category_id}/{obj_id} ({self.current_index+1}/{len(self.object_ids)})"
            self.vis.create_window(window_name=window_title)

            # Automatically move to next mesh
            print("Moving to next mesh automatically")
            if self.current_index < len(self.object_ids) - 1:
                self.current_index += 1
                self.load_current_meshes()
            else:
                print("Already at the last mesh")
                self.show_mesh_check_results()

            return

        # MVS exists
        try:
            recon_mesh = o3d.io.read_triangle_mesh(recon_path)
            if self.notext is True:
                print("NOOOOOOOOOOOOOOOOO TExture")
                recon_mesh.textures.clear()
                recon_mesh.triangle_uvs.clear()
                # recon_mesh.paint_uniform_color([0.8, 0.8, 0.8])  # 浅灰色v
            if len(recon_mesh.vertices) == 0:
                print(f"Reconstructed mesh has not enough vertices: {recon_path}")
                self.record_invalid_mesh(category_id, obj_id, "MVS mesh invalid")
                self.failure_ids.append(obj_id)
                self.invalid_mvs += 1

                # Update checkpoint
                self.update_checkpoint()

                # Update the window title to indicate the mesh is invalid
                window_title = f"[MVS INVALID] {category_id}/{obj_id} ({self.current_index+1}/{len(self.object_ids)})"
                self.vis.create_window(window_name=window_title)

                # Automatically move to next mesh
                print("Moving to next mesh automatically")
                if self.current_index < len(self.object_ids) - 1:
                    self.current_index += 1
                    self.load_current_meshes()
                else:
                    print("Already at the last mesh")
                    self.show_mesh_check_results()

                return

            # Normalize the reconstructed mesh to fit within a unit sphere
            # recon_mesh = self.normalize_mesh(recon_mesh)
            recon_mesh.compute_vertex_normals()

            # Modification
            recon_mesh.orient_triangles()

            # centralize, shift and rotate the mesh
            recon_mesh = self.modify_mesh(recon_mesh, centralize=True, translation=[0.0, 0.0, 2.0], rotation_y_degrees=180)

            # Color the mesh
            # recon_mesh = self.color_mesh(recon_mesh,)

            try:
                if recon_mesh is not None and not recon_mesh.is_empty():
                    print(f"Adding mesh with {len(recon_mesh.vertices)} vertices and {len(recon_mesh.triangles)} triangles")
                    self.vis.add_geometry(recon_mesh)
                else:
                    print("Mesh is empty or None, not adding to visualizer")
            except Exception as e:
                print(f"Failed to add geometry: {e}")

        except Exception as e:
            print(f"Cannot load MVS mesh {recon_path}: {e}")
            self.record_invalid_mesh(category_id, obj_id, "Load MVS mesh failed")
            self.failure_ids.append(obj_id)
            self.load_mvs_failure += 1

            # Update checkpoint
            self.update_checkpoint()

            # Update the window title to indicate loading the mesh failed
            window_title = f"[MVS LOAD FAILED] {category_id}/{obj_id} ({self.current_index+1}/{len(self.object_ids)})"
            self.vis.create_window(window_name=window_title)

            # Automatically move to next mesh
            print("Moving to next mesh automatically")
            if self.current_index < len(self.object_ids) - 1:
                self.current_index += 1
                self.load_current_meshes()
            else:
                print("Already at the last mesh")
                self.show_mesh_check_results()

            return

        # Only if the MVS mesh can be loaded correctly, then check if GT mesh can be loaded
        gt_path = os.path.join(self.gt_dir, obj_id, f"pc_norm.obj")
        try:
            if not os.path.exists(gt_path):
                print(f"GT mesh does not exist: {gt_path}")
                self.record_invalid_mesh(category_id, obj_id, "GT mesh not exist")
                self.failure_ids.append(obj_id)

                self.gt_not_exist += 1

                # Update the window title to indicate the GT mesh doesn't exist
                window_title = f"[GT NOT EXIST] {category_id}/{obj_id} ({self.current_index+1}/{len(self.object_ids)})"
                self.vis.create_window(window_name=window_title)

                # Don't need to skip, just show the MVS mesh

            else:
                gt_mesh = o3d.io.read_triangle_mesh(gt_path)
                if len(gt_mesh.vertices) == 0:
                    print(f"GT mesh has not enough vertices: {gt_path}")
                    self.invalid_gt += 1

                    self.record_invalid_mesh(category_id, obj_id, "GT mesh invalid")
                    self.failure_ids.append(obj_id)

                    # Update the window title to indicate the GT mesh is invalid
                    window_title = f"[GT INVALID] {category_id}/{obj_id} ({self.current_index+1}/{len(self.object_ids)})"
                    self.vis.create_window(window_name=window_title)

                    # Don't need to skip, just show the MVS mesh

                else:
                    gt_mesh.compute_vertex_normals()
                    # gt_mesh.paint_uniform_color([0.7, 0.7, 1.0])  # Blue color
                    self.vis.add_geometry(gt_mesh)

                    # If both meshes load successfully, increment success counter
                    self.check_succeed_mesh += 1

                    # Update view title to display current object ID
                    window_title = f"visualizing {category_id}/{obj_id} ({self.current_index+1}/{len(self.object_ids)})"
                    self.vis.create_window(window_name=window_title)

        except Exception as e:
            print(f"Cannot load GT mesh {gt_path}: {e}")
            self.load_gt_failure += 1
            self.record_invalid_mesh(category_id, obj_id, "Load GT mesh failed")
            self.failure_ids.append(obj_id)

            # Update the window title to indicate loading the GT mesh failed
            window_title = f"[GT LOAD FAILED] {category_id}/{obj_id} ({self.current_index+1}/{len(self.object_ids)})"
            self.vis.create_window(window_name=window_title)

            # Don't need to skip, just show the MVS mesh

        # Update renderer
        self.vis.poll_events()
        self.vis.update_renderer()

        # No longer to initialize the view point
        # Initialize the viewpoint to a specific angle
        # !!! Requires Numpy<2.0, tested on Numpy==1.26
        # print(self.vis.get_view_control())
        if "airplane" in self.save_dir:
            if "right_front" in self.save_dir:
                # left airplane
                self.vis.get_view_control().set_front([0, 1, 0])  # 从 Y 轴负方向往原点看
                self.vis.get_view_control().set_lookat([0, 2, 0])  # 看向原点
                self.vis.get_view_control().set_up([0, 0, 1])  # Z 轴朝上
                self.vis.get_view_control().set_zoom(0.7)  # 调整缩放级别
            elif "right_back" in self.save_dir:
                self.vis.get_view_control().set_front([0, 1, 0])  # 从 Y 轴负方向往原点看
                self.vis.get_view_control().set_lookat([0, 2, 0])  # 看向原点
                self.vis.get_view_control().set_up([0, 0, 1])  # Z 轴朝上
                self.vis.get_view_control().set_zoom(0.7)  # 调整缩放级别
            else:
                # self.vis.get_view_control().set_front([2, -1, 10])  # 从 Y 轴负方向往原点看
                # self.vis.get_view_control().set_lookat([0, 1, 0])  # 看向原点
                # self.vis.get_view_control().set_up([0, 0, 1])  # Z 轴朝上
                # self.vis.get_view_control().set_zoom(0.7)  # 调整缩放级别
                self.vis.get_view_control().set_front([0, 1, 0])  # 从 Y 轴负方向往原点看
                self.vis.get_view_control().set_lookat([0, -2, 0])  # 看向原点
                self.vis.get_view_control().set_up([0, 0, -1])  # Z 轴朝上
                self.vis.get_view_control().set_zoom(1.0)  # 调整缩放级别

        elif "sofa" in self.save_dir and 'left_back' in self.save_dir:
            self.vis.get_view_control().set_front([0, 1, 0])  # 从 Y 轴负方向往原点看
            self.vis.get_view_control().set_lookat([0, 2, 0])  # 看向原点
            self.vis.get_view_control().set_up([0, 0, 1])  # Z 轴朝上
            self.vis.get_view_control().set_zoom(0.7)  # 调整缩放级别
            

        elif "watercraft" in self.save_dir:
            if "right_front" in self.save_dir:
                # left airplane
                self.vis.get_view_control().set_front([0, 1, 0])  # 从 Y 轴负方向往原点看
                self.vis.get_view_control().set_lookat([0, 2, 0])  # 看向原点
                self.vis.get_view_control().set_up([0, 0, 1])  # Z 轴朝上
                self.vis.get_view_control().set_zoom(0.7)  # 调整缩放级别
            elif "right_back" in self.save_dir:
                self.vis.get_view_control().set_front([0, 1, 0])  # 从 Y 轴负方向往原点看
                self.vis.get_view_control().set_lookat([0, 2, 0])  # 看向原点
                self.vis.get_view_control().set_up([0, 0, 1])  # Z 轴朝上
                self.vis.get_view_control().set_zoom(0.7)  # 调整缩放级别
            elif "left_back" in self.save_dir:
                self.vis.get_view_control().set_front([0, 1, 12])  # 从 Y 轴负方向往原点看
                self.vis.get_view_control().set_lookat([0, 0, 1])  # 看向原点
                self.vis.get_view_control().set_up([0, 0, -1])  # Z 轴朝上
                self.vis.get_view_control().set_zoom(1.0)  # 调整缩放级别
            elif "left_front" in self.save_dir:
                self.vis.get_view_control().set_front([0, 1, 12])  # 从 Y 轴负方向往原点看
                self.vis.get_view_control().set_lookat([0, 0, 1])  # 看向原点
                self.vis.get_view_control().set_up([0, 0, -1])  # Z 轴朝上
                self.vis.get_view_control().set_zoom(1.0)  # 调整缩放级别

        elif "table" in self.save_dir:
            if "left_back" in self.save_dir:
                # self.vis.get_view_control().set_front([-8, 4, 10])  # Looking along -Z axis
                # self.vis.get_view_control().set_lookat([0, 0, 0])  # Looking at origin
                # self.vis.get_view_control().set_up([0, 2, 0])  # Y axis is up
                # self.vis.get_view_control().set_zoom(0.7)  # Adjust zoom level as needed
                self.vis.get_view_control().set_front([-3, 1, 0])  # 从 Y 轴负方向往原点看
                self.vis.get_view_control().set_lookat([0, 2, 0])  # 看向原点
                self.vis.get_view_control().set_up([0, 0, 1])  # Z 轴朝上
                self.vis.get_view_control().set_zoom(0.7)  # 调整缩放级别
            elif "left_front" in self.save_dir:
                self.vis.get_view_control().set_front([3, 1, 0])  # 从 Y 轴负方向往原点看
                self.vis.get_view_control().set_lookat([0, 2, 0])  # 看向原点
                self.vis.get_view_control().set_up([0, 0, 1])  # Z 轴朝上
                self.vis.get_view_control().set_zoom(0.7)  # 调整缩放级别
        else:
            if "right_front" in self.save_dir:
                # left table cabinet car sofa chair
                self.vis.get_view_control().set_front([10, 5, -8])  # Looking along -Z axis
                self.vis.get_view_control().set_lookat([0, 0, 0])  # Looking at origin
                self.vis.get_view_control().set_up([0, 2, 0])  # Y axis is up
                self.vis.get_view_control().set_zoom(0.7)  # Adjust zoom level as needed
            elif "right_back" in self.save_dir:
                # right car
                self.vis.get_view_control().set_front([-10, 5, -6])  # Looking along -Z axis
                self.vis.get_view_control().set_lookat([0, 0, 0])  # Looking at origin
                self.vis.get_view_control().set_up([0, 2, 0])  # Y axis is up
                self.vis.get_view_control().set_zoom(0.7)  # Adjust zoom level as needed 
            elif "left_front" in self.save_dir:
                self.vis.get_view_control().set_front([12, 5, 12])  # Looking along -Z axis
                self.vis.get_view_control().set_lookat([0, 0, 0])  # Looking at origin
                self.vis.get_view_control().set_up([0, 2, 0])  # Y axis is up
                self.vis.get_view_control().set_zoom(1.0)  # Adjust zoom level as needed
            elif "left_back" in self.save_dir:
                self.vis.get_view_control().set_front([-12, 5, 10])  # Looking along -Z axis
                self.vis.get_view_control().set_lookat([0, 0, 0])  # Looking at origin
                self.vis.get_view_control().set_up([0, 2, 0])  # Y axis is up
                self.vis.get_view_control().set_zoom(1.0)  # Adjust zoom level as needed

        self.vis.update_renderer()

        print(f"Loaded mesh: {window_title}")

    def next_mesh(self, vis):
        """Visualize next mesh"""
        print("Next mesh key pressed")
        if self.current_index < len(self.object_ids) - 1:
            # Record that we finished reviewing the current mesh
            self.update_checkpoint()
            self.update_reults()

            self.current_index += 1
            self.load_current_meshes()
        else:
            print("Already at the last mesh")
            self.show_mesh_check_results()
        return False

    # def prev_mesh(self, vis):
    #     """Recall function to visualize previous mesh.
    #     Useful when user mistakenly confirms the quality of the previous mesh
    #     and wants to go back to the previous mesh."""
    #     print("Previous mesh key pressed")
    #     if self.current_index > 0:
    #         # Remove last checkpoint since we're going back
    #         self.update_checkpoint(add=False)

    #         self.current_index -= 1
    #         self.load_current_meshes()
    #     else:
    #         print("Already at the first mesh")
    #         # Force lift the root window to top to show message box
    #         self.root.deiconify()
    #         self.root.lift()
    #         self.root.attributes('-topmost', True)
    #         messagebox.showinfo("Info", "Already at the first mesh")
    #         self.root.attributes('-topmost', False)
    #         self.root.withdraw()
    #     return False

    def prev_mesh(self, vis):
        """Recall function to visualize previous mesh.
        Useful when user mistakenly confirms the quality of the previous mesh
        and wants to go back to the previous mesh."""
        print("Previous mesh key pressed")
        if self.current_index > 0:
            # Remove last checkpoint since we're going back
            self.update_checkpoint(add=False)

            # Go to previous mesh
            self.current_index -= 1

            # Try to load the mesh, if it fails (doesn't exist), keep going back
            max_attempts = self.current_index + 1  # Prevent infinite loop
            attempts = 0

            while attempts < max_attempts:
                # Create a backup of the counters before loading
                backup_counters = {
                    "gt_not_exist": self.gt_not_exist,
                    "mvs_not_exist": self.mvs_not_exist,
                    "invalid_mvs": self.invalid_mvs,
                    "load_mvs_failure": self.load_mvs_failure,
                    "invalid_gt": self.invalid_gt,
                    "load_gt_failure": self.load_gt_failure,
                    "check_succeed_mesh": self.check_succeed_mesh,
                }

                # Try to load the current mesh
                current_obj_id = self.object_ids[self.current_index]
                print(f"Trying to load previous mesh: {self.category_id}/{current_obj_id}")

                # Check if the reconstructed mesh exists
                recon_path = os.path.join(self.recon_dir, current_obj_id, "Tile_00000_mesh.ply")
                poisson_recon_path = os.path.join(self.recon_dir, current_obj_id, "Tile_00000_pcloud_poisson.ply")
                if os.path.exists(poisson_recon_path):
                    recon_path = poisson_recon_path

                if not os.path.exists(recon_path):
                    print(f"Previous MVS mesh doesn't exist: {recon_path}, skipping further back")
                    # Remove the additional checkpoint update since we're skipping this mesh
                    self.update_checkpoint(add=False)

                    # If we're at the first mesh already, break
                    if self.current_index <= 0:
                        print("Reached the first mesh, stopping")
                        break

                    # Go to previous mesh
                    self.current_index -= 1
                    attempts += 1
                    continue

                # If we get here, the mesh exists, break the loop
                print(f"Found valid previous mesh: {self.category_id}/{current_obj_id}")
                # Restore counters to prevent double-counting
                self.gt_not_exist = backup_counters["gt_not_exist"]
                self.mvs_not_exist = backup_counters["mvs_not_exist"]
                self.invalid_mvs = backup_counters["invalid_mvs"]
                self.load_mvs_failure = backup_counters["load_mvs_failure"]
                self.invalid_gt = backup_counters["invalid_gt"]
                self.load_gt_failure = backup_counters["load_gt_failure"]
                self.check_succeed_mesh = backup_counters["check_succeed_mesh"]

                # Load the valid previous mesh
                self.load_current_meshes()
                break

            # If we've gone through all attempts and couldn't find a valid mesh
            if attempts >= max_attempts:
                print("Couldn't find a valid previous mesh after multiple attempts")
                # Force lift the root window to top to show message box
                self.root.deiconify()
                self.root.lift()
                self.root.attributes("-topmost", True)
                messagebox.showinfo("Info", "Couldn't find a valid previous mesh")
                self.root.attributes("-topmost", False)
                self.root.withdraw()
        else:
            print("Already at the first mesh")
            # Force lift the root window to top to show message box
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            messagebox.showinfo("Info", "Already at the first mesh")
            self.root.attributes("-topmost", False)
            self.root.withdraw()
        return False

    def handle_d_key(self, vis):
        """Handler for d key, immediately records the current mesh as unsatisfactory"""
        print("d pressed")
        obj_id = self.object_ids[self.current_index]
        category_id = self.category_id

        # Record as unsatisfactory immediately without confirmation
        print("record unsatisfcatory")
        self.record_invalid_mesh(category_id, obj_id, "mesh unsatisfactory")
        self.failure_ids.append(obj_id)

        print(f"D key pressed - Recorded unsatisfactory mesh: {category_id}/{obj_id}")

        # Move to next mesh automatically
        if self.current_index < len(self.object_ids) - 1:
            self.update_checkpoint()
            self.current_index += 1
            self.load_current_meshes()

        return False

    def record_invalid_mesh(self, category_id, obj_id, reason):
        """Record unsatisfactory mesh to CSV file"""
        # First check if this object has already been processed in a previous session
        record_key = (category_id, obj_id)
        if record_key in self.previous_records:
            if reason == self.previous_records[record_key]:
                print(f"Record already exists in previous sessions: {category_id}/{obj_id}")
                return

        # Check if this mesh has already been recorded in the current session to avoid duplicates
        already_recorded = False
        updated_rows = []

        if os.path.exists(self.results_file):
            with open(self.results_file, "r", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)  # Store header row

                if header:
                    # Add header to updated_rows
                    updated_rows.append(header)

                    # Process all rows, skip those with matching ID but different reason
                    for row in reader:
                        if len(row) >= 3 and row[0] == category_id and row[1] == obj_id:
                            if row[2] == reason:
                                already_recorded = True
                                updated_rows.append(row)  # Keep the row as is
                            else:
                                # Skip the row with old reason (effectively deleting it)
                                old_reason = row[2]
                                print(f"Updating record: {category_id}/{obj_id} - {old_reason} -> {reason}")
                                # Don't append this row to updated_rows
                        else:
                            updated_rows.append(row)  # Keep other rows

        # If not already recorded, add the new record
        if not already_recorded:
            # Create the file with header if it doesn't exist
            if not os.path.exists(self.results_file):
                updated_rows = [["category_id", "obj_id", "reason"]]

            # Add the new record
            updated_rows.append([category_id, obj_id, reason])
            print(f"Recorded: {category_id}/{obj_id} - {reason}")

            # Update previous records to avoid duplicate recording
            self.previous_records[record_key] = reason

            # Write all rows back to the file
            with open(self.results_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(updated_rows)
        else:
            print(f"Record already exists in current session: {category_id}/{obj_id}")

    def debounce_key(self, callback_func, log_only=False):
        """Decorator function to prevent key press repeats"""

        def debounced_callback(vis, *args):
            current_time = datetime.now().timestamp()
            time_since_last_press = current_time - self.last_key_time

            # If time interval is greater than cooldown time, execute the callback
            if time_since_last_press > self.key_cooldown:
                self.last_key_time = current_time
                if not log_only:
                    return callback_func(vis, *args)
                else:
                    callback_func(vis, *args)
                    return False
            else:
                print(f"Key press ignored, interval too short: {time_since_last_press:.2f} seconds")
                return False

        return debounced_callback

    def print_key_code(self, vis, key, mod):
        """Print key code for debugging key bindings"""
        print(f"Key pressed: {key}")
        return False

    def run(self):
        """Start visualization loop"""
        print("Control instructions:")
        print("Space key: Next mesh")
        print("Left arrow key: Previous mesh (undo function)")
        print("'d' key: Mark current mesh as unsatisfactory and automatically move to next mesh")
        print("'q' or ESC key: Exit the application")
        print("Press any key to see its key code (for debugging)")

        # Need to update root window to handle dialogs correctly with Open3D
        def update_tk():
            try:
                self.root.update()
                self.root.after(100, update_tk)
            except tk.TclError:
                # This happens when the window is destroyed
                print("Tkinter window was destroyed")
                return

        # Start the Tkinter update loop
        self.root.after(0, update_tk)

        # Run the Open3D visualization loop
        self.vis.run()

        # Cleanup
        try:
            self.vis.destroy_window()
        except:
            pass

        try:
            self.root.destroy()
        except:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mesh Viewer Application")
    parser.add_argument("--category", type=str, required=True, help="Model category")
    parser.add_argument("--side", type=str, required=True, help="View side (left or right)")
    parser.add_argument(
        "--test", action="store_true", default=False, help="Help testing the second round, as if meshes are updated"
    )
    parser.add_argument(
        "--notexture", action="store_true", default=False, help="Help testing the second round, as if meshes are updated"
    )
    # Now check that the reboot has completed automatically
    # parser.add_argument('--restart', action='store_true', default=False,
    #                 help='Clear previously checked mesh IDs from checkpoint to enable re-checking of updated meshes. '
    #                      'Use this flag when you have fixed problem meshes and need to run a manual check again. '
    #                      'Checkpoint data is still maintained to prevent duplicate checks if the program crashes.')
    args = parser.parse_args()

    category_id_dict = {
        "airplane": "02691156",
        "cabinet": "02933112",
        "car": "02958343",
        "chair": "03001627",
        "lamp": "03636649",
        "sofa": "04256520",
        "table": "04379243",
        "watercraft": "04530566",
    }

    category = args.category
    category_id = category_id_dict[category]
    object_side = args.side
    test = args.test
    notext = args.notexture
    if object_side in ['left_front', 'left_back', 'right_front', 'right_back', 'left', 'right']:
        app = MeshViewerApp(category, category_id, object_side, test, notext=notext)
    else:
        print("object side must be one from ['left_front', 'left_back', 'right_front', 'right_back'], current object side invalid")
