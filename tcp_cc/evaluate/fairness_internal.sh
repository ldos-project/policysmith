#!/bin/bash

REPO_DIR="/home/ardula/dumbsearch/evaluate"
TRACE192="$REPO_DIR/sage_traces/traces/wired192"

TYPE=$1
NUM_FLOWS=$2
TOTAL_DURATION=$3

GAP_BETWEEN_FLOWS=$(( TOTAL_DURATION / NUM_FLOWS ))


for ((i=0; i<NUM_FLOWS; i++)); do
  LOG_PATH="$REPO_DIR/results/flow$((i+1))"

  if [[ $TYPE == "iperf3" ]]; then
    port=$((30000+i))
    FLOW_DURATION=$(( TOTAL_DURATION - i * GAP_BETWEEN_FLOWS ))
    mm-link "$TRACE192" "$TRACE192" --uplink-log="$LOG_PATH" -- \
      bash -c "LD_PRELOAD=./src/nodelay.so iperf3 -p $port -c \$MAHIMAHI_BASE -t $FLOW_DURATION || true" &
    echo "[internal] Launching iperf3 flow $((i+1)) for $FLOW_DURATION seconds"
  elif [[ $TYPE == "tcp_eval" ]]; then
    port=$((44444+i))
    mm-link "$TRACE192" "$TRACE192" --downlink-log="$LOG_PATH" -- \
      bash -c "./src/client.o \$MAHIMAHI_BASE $port" &
    echo "[internal] Launching client $((i+1))"
  else
    echo "[internal] unsupported type: $TYPE"
  fi

  if (( i < NUM_FLOWS - 1 )); then
    sleep $GAP_BETWEEN_FLOWS
  fi
done



wait