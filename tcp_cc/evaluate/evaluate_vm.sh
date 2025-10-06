set -x

VM_NAME=$1
DELAY=$2
TRACE=$3
BDP_MULTIPLIER=$4
TOTAL_DURATION=$5

trace_name=delay${DELAY}_${TRACE}_${BDP_MULTIPLIER}bdp_dur${TOTAL_DURATION}

if [[ "$TRACE" == "ATT-LTE-driving-2016.down" || "$TRACE" == "TMobile-LTE-short.down" || "$TRACE" == "Verizon-LTE-short.down" ]]; then
    bw=50
else
    bw=$(echo $TRACE | grep -oP 'wired\K\d+')
fi
bdp=$(echo "2 * $bw * $DELAY / 12.0" | bc -l)
qs=$(echo "$BDP_MULTIPLIER * $bdp" | bc -l | awk '{print int($1)}')

sudo pkill iperf3

i=$(echo "$VM_NAME" | grep -oP '\d+$')
iperf3 -s -p $((30000+i)) > /dev/null 2>&1 &
sleep 1

rm -rfv ~/logs && mkdir -p ~/logs
mm-delay $DELAY mm-link ~/traces/$TRACE ~/traces/wired192 --uplink-queue-args="packets=$qs"  --downlink-queue-args="packets=$qs" --uplink-queue=droptail --downlink-queue=droptail --uplink-log=$HOME/logs/down-$trace_name -- bash evaluate_internal.sh $((30000+i)) $TOTAL_DURATION
echo "[vm] done with flow"

sudo pkill iperf3