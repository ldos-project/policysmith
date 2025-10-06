#!/bin/bash
TRACE="/home/ardula/dumbsearch/evaluate/sage_traces/traces/wired96"
TRACE192="/home/ardula/dumbsearch/evaluate/sage_traces/traces/wired192"

TYPE=$1
NUM_FLOWS=2
TOTAL_DURATION=10

if (( TOTAL_DURATION % NUM_FLOWS != 0 )); then
  echo "Error: TOTAL_DURATION must be divisible by NUM_FLOWS"
  exit 1
fi

GAP_BETWEEN_FLOWS=$(( TOTAL_DURATION / NUM_FLOWS ))
delay=20
bdp_multiplier=0.5
bw=$(echo $TRACE | grep -oP 'wired\K\d+')
bdp=$(echo "2 * $bw * $delay / 12.0" | bc -l)
qs=$(echo "$bdp_multiplier * $bdp" | bc -l | awk '{print int($1)}')

if [[ $TYPE == "iperf3" ]]; then
    pkill iperf3
    for ((i=0; i<NUM_FLOWS; i++)); do
        iperf3 -s -p $((30000+i)) 2>&1 &
    done
    mm-delay 10 mm-link $TRACE $TRACE192 --uplink-queue-args="packets=$qs"  --downlink-queue-args="packets=$qs" --uplink-queue=droptail --downlink-queue=droptail --uplink-log=/home/ardula/dumbsearch/evaluate/results/flowTOT -- bash fairness_internal.sh $TYPE $NUM_FLOWS $TOTAL_DURATION
elif [[ $TYPE == "tcp_eval" ]]; then
    pkill client.o tcp_eval.o

    for ((i=0; i<NUM_FLOWS; i++)); do
        FLOW_DURATION=$(( TOTAL_DURATION - i * GAP_BETWEEN_FLOWS ))
        ./src/tcp_eval.o $((44444+i)) cubic $FLOW_DURATION 2>&1 &
        echo "Launching tcp_eval.o flow $((i+1)) for $FLOW_DURATION seconds"
    done

    mm-delay 10 mm-link $TRACE192 $TRACE --uplink-queue-args="packets=$qs"  --downlink-queue-args="packets=$qs" --uplink-queue=droptail --downlink-queue=droptail --downlink-log=/home/ardula/dumbsearch/evaluate/results/flowTOT -- bash fairness_internal.sh $TYPE $NUM_FLOWS $TOTAL_DURATION
else
    echo "Unsupported"
    exit
fi


pkill iperf3