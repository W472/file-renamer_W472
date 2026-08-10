# backend/app.py
import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 允许跨域，前后端分离必备

# 【安全】建议限制可操作的根目录，防止误操作系统文件
BASE_DIR = os.path.expanduser("~")   # 仅允许操作用户家目录
# BASE_DIR = "/your/safe/path"       # 也可自定义

@app.route('/api/files', methods=['GET'])
def list_files():
    """扫描目录，返回文件名列表（仅文件，不含子目录）"""
    path = request.args.get('path', '')
    # 安全检查：必须在 BASE_DIR 下
    full_path = os.path.abspath(os.path.join(BASE_DIR, path))
    if not full_path.startswith(os.path.abspath(BASE_DIR)):
        return jsonify({'error': '路径超出允许范围'}), 403
    
    if not os.path.isdir(full_path):
        return jsonify({'error': '目录不存在'}), 404

    try:
        files = [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]
        return jsonify({'path': full_path, 'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/preview', methods=['POST'])
def preview_rename():
    data = request.get_json()
    path = data.get('path', '')
    files_raw = data.get('files', [])
    rule = data.get('rule', {})

    full_path = os.path.abspath(os.path.join(BASE_DIR, path))
    # ... 安全校验同上 ...

    preview = []
    for idx, file_obj in enumerate(files_raw):
        if isinstance(file_obj, str):
            filename = file_obj
            index = idx
        else:
            filename = file_obj.get('name', '')
            index = file_obj.get('index', idx)
        
        old_full = os.path.join(full_path, filename)
        if not os.path.isfile(old_full):
            continue
        # 为编号规则传入索引
        rule_with_index = dict(rule)
        rule_with_index['index'] = index
        new_name = apply_rule(filename, rule_with_index)
        preview.append({'old': filename, 'new': new_name})
    # ... 后续冲突检测不变 ...

@app.route('/api/execute', methods=['POST'])
def execute_rename():
    """执行重命名"""
    data = request.get_json()
    path = data.get('path', '')
    renames = data.get('renames', [])   # [{old, new}, ...]

    full_path = os.path.abspath(os.path.join(BASE_DIR, path))
    if not full_path.startswith(os.path.abspath(BASE_DIR)):
        return jsonify({'error': '路径超出允许范围'}), 403

    results = []
    for item in renames:
        old_name = item['old']
        new_name = item['new']
        old_full = os.path.join(full_path, old_name)
        new_full = os.path.join(full_path, new_name)

        if not os.path.isfile(old_full):
            results.append({'old': old_name, 'new': new_name, 'status': 'error', 'msg': '原文件不存在'})
            continue
        if os.path.exists(new_full):
            results.append({'old': old_name, 'new': new_name, 'status': 'error', 'msg': '目标文件名已存在'})
            continue

        try:
            os.rename(old_full, new_full)
            results.append({'old': old_name, 'new': new_name, 'status': 'success', 'msg': '重命名成功'})
        except Exception as e:
            results.append({'old': old_name, 'new': new_name, 'status': 'error', 'msg': str(e)})

    return jsonify({'results': results})

def apply_rule(filename, rule):
    """根据规则类型生成新文件名"""
    rtype = rule.get('type')
    name, ext = os.path.splitext(filename)
    
    if rtype == 'add_prefix':
        prefix = rule.get('value', '')
        if rule.get('keep_ext', True):
            return prefix + name + ext
        else:
            return prefix + filename
    
    elif rtype == 'add_suffix':
        suffix = rule.get('value', '')
        if rule.get('keep_ext', True):
            return name + suffix + ext
        else:
            return filename + suffix
    
    elif rtype == 'replace':
        old_text = rule.get('old_text', '')
        new_text = rule.get('new_text', '')
        if rule.get('keep_ext', True):
            new_name = name.replace(old_text, new_text) + ext
        else:
            new_name = filename.replace(old_text, new_text)
        return new_name
    
    elif rtype == 'regex_replace':
        pattern = rule.get('pattern', '')
        repl = rule.get('replacement', '')
        try:
            if rule.get('keep_ext', True):
                new_name = re.sub(pattern, repl, name) + ext
            else:
                new_name = re.sub(pattern, repl, filename)
        except re.error:
            return filename   # 正则错误时返回原名
        return new_name
    
    elif rtype == 'numbering':
        index = rule.get('index', 0)   # 文件在列表中的索引（0开始）
        start = rule.get('start', 1)
        digits = rule.get('digits', 3)
        prefix = rule.get('prefix', '')
        num = start + index
        num_str = str(num).zfill(digits)
        if rule.get('keep_ext', True):
            return f"{prefix}{num_str}{ext}"
        else:
            return f"{prefix}{num_str}"
    
    else:
        return filename   # 未知规则，保持原名

if __name__ == '__main__':
    # 启动后端服务，端口5000
    app.run(debug=True, port=5000)