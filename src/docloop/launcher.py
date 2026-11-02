"""双击启动的中文控制台演示，不自动审批任何 Spec。"""
import json
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from .project import inspect_project
from .workflow import Workflow


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding='utf-8')
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    print('DocLoop 项目框架 · 受控离线演示\n')
    print('1. 正常流程演示  2. 验证失败演示  3. 查看配置检查  0. 退出')
    choice = input('请选择 [1]：').strip() or '1'
    if choice == '0':
        return
    if choice == '3':
        print(json.dumps(inspect_project(root), ensure_ascii=False, indent=2))
        return
    if choice not in {'1', '2'}:
        raise ValueError('请输入 0、1、2 或 3')
    change_id = 'demo-' + datetime.now().strftime('%Y%m%d-%H%M%S-') + uuid4().hex[:6]
    scenario = 'success' if choice == '1' else 'verification-failure'
    with Workflow(root) as flow:
        flow.start(change_id, '# 受控演示 Spec\n\n'
                   'AC-001：沙箱 result.json 中 value=42，验证者重新执行检查。\n'
                   '本演示仅检查工作流，不代表真实业务功能验收。\n', scenario, mode='demo')
        path = flow.gov.path(change_id) / 'spec.md'
        print('\n' + path.read_text(encoding='utf-8'))
        digest = flow.gov.digest(change_id)
        print(f'Spec：{path}\nSHA256：{digest}\nChange ID：{change_id}')
        if input('\n审阅后输入 APPROVE 明确批准本 Spec，其他输入保留草稿：').strip() != 'APPROVE':
            print('已保留草稿与 Checkpoint。以后可通过 CLI 审批继续。')
            return
        result = flow.approve(change_id, digest, 'local-console-user')
        print(f'\n演示状态：{result["status"]}（mode=demo）')
        if result.get('error'):
            print('原因：' + result['error'])
        print(f'产物目录：{flow.gov.path(change_id)}')
        if result.get('archive'):
            print('归档：' + result['archive'])


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f'启动失败：{error}', file=sys.stderr)
        raise SystemExit(2)
