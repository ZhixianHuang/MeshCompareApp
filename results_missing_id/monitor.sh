#!/bin/bash

# 监控连续包含"Loaded mesh"的行并提取路径
OUTPUT_FILE="/home/huangzhixian/mesh3d/SDFusion/results_missing_id/left_front_lamp.txt"
LAST_WAS_LOADED_MESH=false

echo "开始监控连续包含'Loaded mesh'的行，按 Ctrl+C 停止..."

while IFS= read -r line; do
    echo "$line"
    
    if [[ "$line" == *"Loaded mesh"* ]]; then
        if [[ "$LAST_WAS_LOADED_MESH" == true ]]; then
            # 提取路径部分：从"visualizing "后面到第一个空格
            temp="${line#*visualizing }"
            mesh_path="${temp%% *}"
            
            # timestamp=$(date '+%Y-%m-%d %H:%M:%S')
            echo "$mesh_path" >> "$OUTPUT_FILE"
            echo "🔍 记录路径: $mesh_path" >&2
        fi
        LAST_WAS_LOADED_MESH=true
    else
        LAST_WAS_LOADED_MESH=false
    fi
done