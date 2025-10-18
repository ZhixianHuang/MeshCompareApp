import os
import argparse

def delete_missing_ids(cate, side):
    target_dir = "/home/huangzhixian/mesh3d/SDFusion/results"
    source_dir = "/home/huangzhixian/mesh3d/SDFusion/results_missing_id"

    src_file = None
    for file in os.listdir(source_dir):
        if cate in file and side in file:
            src_file = file
            print(src_file)
            break

    targ_file = None
    for file in os.listdir(target_dir):
        if cate in file and side in file and file.endswith('txt'):
            targ_file = file
            print(targ_file)
            break

    if src_file is None or targ_file is None:
        print("File not found.")
        return

    src_path = os.path.join(source_dir, src_file)
    targ_path = os.path.join(target_dir, targ_file)

    with open(src_path, 'r') as f:
        missing_ids = set([
    line.strip().split('/')[-1] if '/' in line else line.strip()
    for line in f
        ])
    # print(len(missing_ids))

    with open(targ_path, 'r') as f:
        existing_ids = [line.strip() for line in f]

    # print(len(existing_ids))
    found_ids = [id for id in missing_ids if id in existing_ids]
    # print(len(found_ids))
    if len(found_ids) == len(missing_ids):
        print("Missing ids found, start delete!")
    # 剩余未匹配的
    missing_ids = [id for id in missing_ids if id not in found_ids]
    existing_ids = [id for id in existing_ids if id not in found_ids]

    # 重写
    with open(targ_path, 'w') as f:
        for id in existing_ids:
            f.write(f"{id}\n")

    with open(src_path, 'w') as f:
        for id in missing_ids:
            f.write(f"{id}\n")
    
    print("Missing ids deleted!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mesh Viewer Application")
    parser.add_argument("--category", type=str, required=True, help="Model category")
    parser.add_argument("--side", type=str, required=True, help="View side (left or right)")
    args = parser.parse_args()

    cate = args.category
    side = args.side
    delete_missing_ids(cate=cate, side=side)