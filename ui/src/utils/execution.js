export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function runNodeSequence({
  sequence,
  delayMs = 550,
  getOutputKey,
  getOutputValue,
  onNodeStart,
  onNodeComplete,
  onSequenceDone,
}) {
  for (const nodeId of sequence) {
    onNodeStart?.(nodeId);
    await sleep(delayMs);
    const outputKey = getOutputKey(nodeId);
    const outputValue = getOutputValue(outputKey);
    onNodeComplete?.(nodeId, outputValue);
  }
  onSequenceDone?.();
}
