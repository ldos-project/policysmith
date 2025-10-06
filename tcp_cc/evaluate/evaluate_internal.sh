PORT=$1
DURATION=$2

echo "mmbase=$MAHIMAHI_BASE $PORT $DURATION"

cd ~/utils
sudo LD_PRELOAD=./heuristic.so iperf3 -c $MAHIMAHI_BASE -p $PORT -t $DURATION > /dev/null 2>&1