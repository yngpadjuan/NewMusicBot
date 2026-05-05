#!/bin/bash

DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
echo $DIR

BACKUP_1=$DIR/MusicFiles/website/script/
BACKUP_2=$DIR/BackUpDisk/website/script

cp $DIR/*.py $BACKUP_1
cp $DIR/*.sh $BACKUP_1
cp $DIR/*.conf $BACKUP_1
cp -r $DIR/serviceFiles $BACKUP_1

cp $DIR/*.py $BACKUP_2
cp $DIR/*.sh $BACKUP_2
cp $DIR/*.conf $BACKUP_2
cp -r $DIR/serviceFiles $BACKUP_2
