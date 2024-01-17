if [ "$#" -ne 2 ]
then
    echo "Usage: trans <language> <destination>"
else
    lang=$1
    dest=$2
    trubar --conf $lang/trubar-config.yaml translate -s ../orangewidget -d $dest/orangewidget $lang/msgs.jaml
fi
