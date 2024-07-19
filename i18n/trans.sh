if [ "$#" -ne 1 ]
then
    echo "trans <destination>"
    exit
else
    dest=$1
    trubar --conf trubar-config.yaml translate -s ../orangewidget -d $dest/orangewidget msgs.jaml
fi
