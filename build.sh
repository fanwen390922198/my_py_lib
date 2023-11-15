#rm -f ees_manager-*.rpm

code_path=$(pwd)
echo "当前目录: " $code_path

current_version=$(cat $code_path/ees_manager/__init__.py |awk '{print $3}'|sed 's/\"//g'|sed 's/\r//g')
echo "当前版本: " $current_version

echo "中英文 mo、po 文件转换"
cd $code_path/ees_manager/locale/zh_CN/LC_MESSAGES/
msgfmt -o ees_manager.mo  ees_manager.po

cd $code_path/ees_manager/locale/en_GB/LC_MESSAGES/
msgfmt -o ees_manager.mo  ees_manager.po

cd $code_path

echo "ees_manager 编译打包"
python3 setup.py bdist_rpm --force-arch x86_64

cp ./dist/ees_manager-$current_version-1.x86_64.rpm ./

