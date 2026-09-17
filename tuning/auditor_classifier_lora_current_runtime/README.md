# One current-runtime rebase and final classifier training attempt

Authorization: attachment `dcfd3146-30c0-488e-bfaa-43bf99428397`. One A10, $2.50 soft/$3.50 hard, no retry. The previous attempts and seals remain immutable.

The payload contains the existing 2,040 classifier records, schedule/challenges, the historical step120 adapter/config, pinned acquisition metadata and code. It excludes all old cached features, head weights, mean/std and cached logits. The 16 existing control IDs are retained without old expected outputs. Optional update0 DEV evaluation is omitted.

One live model extracts 1,792 TRAIN features in eval/inference mode; FP32 population mean/std (clamp1e-6) are fitted only on those rows. A single new four-way head receives exactly 200 full-population Adam updates at LR.01 from zero with seed7 and regularization .001*mean(W^2). Each update repeats its forward and gradient calculation from the same parameter state and requires bitwise identity before its one optimizer step. Deterministic Torch algorithms are enabled. This verifies arithmetic repeatability without a second candidate or a second head-fit trajectory. All losses/gradients/parameters must be finite.

TRAIN-only sanity is fixed before launch: accuracy>=.50, macroF1>=.50, CE<ln4. This is a head-fit sanity margin above uniform chance, not a DEV selection threshold. After the fit, the historical adapter is copied into the classifier fork; loaded tensors match the source inventory. Current-reference/current-fork controls must agree at rtol1e-4/atol2e-4. The reference is then removed. A new full-TRAIN no-grad pass must reproduce the current fitted-head predictions/metrics and mean CE within max(1e-4,1%) of Phase4. No historical cached CE/logits are admission anchors.

Joint optimization and instrumentation are unchanged. Before update1, bind mean-update CE ceiling=max(10*ln4,20*CURRENT_UPDATE0_CE), microbatch ceiling=4x. Exactly20 stable updates admit continuation; no DEV at20, no skips/retries. Total896 updates and both448/896 quality evaluations are mandatory. Current mean/std remain fixed and their hashes accompany every checkpoint. Selection retains all original co-primary gates and tie-breaks.

Budget projection: setup/load900s, TRAIN features896s, head60s, controls16s, full TRAIN baseline896s, joint5376s, DEV248s, hashes/evidence240s, termination reserve600s:9232s (~154min), $3.308133 at $1.29/hour. Runtime gates use measured feature/update time; independent watchdog terminates before hard ceiling. No provisioning if live pricing/capacity or the full-work estimate is unsuitable.

One-off diagnostic exception only: V2 remains NOT_READY, HOLDOUT unconsumed, Producer/protected/generation/full-pipeline/governance/multi-round excluded. After numerical failure, stop this training path. After valid complete quality failure, stop this base/task formulation. No further automatic experiment or integration validation.
