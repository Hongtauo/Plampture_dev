# -*- mode: python ; coding: utf-8 -*-
"""
Plampture 项目打包配置文件
使用方法: pyinstaller Plampture.spec
"""

block_cipher = None

# 分析 setup.py 的依赖
setup_analysis = Analysis(
    ['setup.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icon', 'icon'),  # 打包 icon 文件夹
    ],
    hiddenimports=[
        'Setup_ui',
        'snapshot_io',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 添加 VC++ 运行时库
import os
import sys
vcruntime_dll = os.path.join(sys.base_prefix, 'vcruntime140.dll')
if os.path.exists(vcruntime_dll):
    setup_analysis.binaries.append(('vcruntime140.dll', vcruntime_dll, 'BINARY'))

vcruntime_1_dll = os.path.join(sys.base_prefix, 'vcruntime140_1.dll')
if os.path.exists(vcruntime_1_dll):
    setup_analysis.binaries.append(('vcruntime140_1.dll', vcruntime_1_dll, 'BINARY'))

# 分析 main.py 的依赖
main_analysis = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('icon', 'icon'),  # 打包 icon 文件夹
    ],
    hiddenimports=[
        'Plampture_ui',
        'dynamic_layout',
        'camera_manager',
        'scan_QRcode',
        'capture',
        'snapshot_io',
        'pygrabber.dshow_graph',
        'pyzbar.pyzbar',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# 添加 VC++ 运行时库（关键修复）
import os
import sys
vcruntime_dll = os.path.join(sys.base_prefix, 'vcruntime140.dll')
if os.path.exists(vcruntime_dll):
    main_analysis.binaries.append(('vcruntime140.dll', vcruntime_dll, 'BINARY'))

vcruntime_1_dll = os.path.join(sys.base_prefix, 'vcruntime140_1.dll')
if os.path.exists(vcruntime_1_dll):
    main_analysis.binaries.append(('vcruntime140_1.dll', vcruntime_1_dll, 'BINARY'))

# 合并两个分析结果，去重
MERGE((setup_analysis, 'setup', 'setup'), (main_analysis, 'main', 'main'))

# 创建 setup.exe
setup_pyz = PYZ(setup_analysis.pure, setup_analysis.zipped_data, cipher=block_cipher)

setup_exe = EXE(
    setup_pyz,
    setup_analysis.scripts,
    [],  # 空列表，使用COLLECT模式
    exclude_binaries=True,  # 关键：使用文件夹模式
    name='setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon\\Plampture.ico',
)

setup_coll = COLLECT(
    setup_exe,
    setup_analysis.binaries,
    setup_analysis.zipfiles,
    setup_analysis.datas,
    strip=False,
    upx=False,
    name='setup',
)

# 创建 main.exe
main_pyz = PYZ(main_analysis.pure, main_analysis.zipped_data, cipher=block_cipher)

main_exe = EXE(
    main_pyz,
    main_analysis.scripts,
    [],  # 空列表，使用COLLECT模式
    exclude_binaries=True,  # 关键：使用文件夹模式
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon\\Plampture.ico',
)

main_coll = COLLECT(
    main_exe,
    main_analysis.binaries,
    main_analysis.zipfiles,
    main_analysis.datas,
    strip=False,
    upx=False,
    name='main',
)
