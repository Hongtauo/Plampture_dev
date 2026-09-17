@echo off
REM Plampture 项目代码规范检查脚本
REM 使用方法: 双击运行或在命令行中执行 check_code.bat

echo ========================================
echo Plampture 代码规范检查工具
echo ========================================
echo.

REM 检查是否安装了必要的工具
echo [1/4] 检查开发工具...
python -c "import black" 2>nul
if errorlevel 1 (
    echo [警告] black 未安装，正在安装...
    pip install black
)

python -c "import isort" 2>nul
if errorlevel 1 (
    echo [警告] isort 未安装，正在安装...
    pip install isort
)

python -c "import flake8" 2>nul
if errorlevel 1 (
    echo [警告] flake8 未安装，正在安装...
    pip install flake8
)

echo [完成] 开发工具检查完成
echo.

REM 格式化代码
echo ========================================
echo [2/4] 正在格式化代码 (Black)...
echo ========================================
black . --exclude "/(Plampture_ui\.py|Setup_ui\.py|workspace|__pycache__)/"
echo.

REM 排序导入
echo ========================================
echo [3/4] 正在排序导入 (isort)...
echo ========================================
isort . --skip Plampture_ui.py --skip Setup_ui.py --skip workspace
echo.

REM 代码检查
echo ========================================
echo [4/4] 正在检查代码 (flake8)...
echo ========================================
flake8
if errorlevel 1 (
    echo.
    echo [警告] 发现代码规范问题，请查看上面的输出
) else (
    echo [成功] 代码检查通过！
)
echo.

echo ========================================
echo 检查完成！
echo ========================================
echo.
echo 提示:
echo - 代码已自动格式化
echo - 如有 flake8 警告，请根据提示修改
echo - 详细使用说明请查看: docs\代码规范工具使用指南.md
echo.

pause
