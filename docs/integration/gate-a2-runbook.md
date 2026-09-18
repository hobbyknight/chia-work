# Gate A.2 — CHIA → Chipyard → GemminiRocketConfig

## Mục tiêu

Gate A.2 chỉ PASS khi một `TypedAction(BUILD)` được SafetyGate cho phép, được thực thi qua CHIA `ChiselBuildNode`, build `GemminiRocketConfig` bằng Chipyard/Verilator, và trả về simulator artifact thật với `mocked=false`.

Pipeline:

```text
TypedAction(BUILD)
  -> SafetyGate
  -> GemminiChiselBuildExecutor
  -> CHIA ChiselBuildNode.build
  -> worker resource {chipyard: 1}
  -> Chipyard GemminiRocketConfig
  -> Verilator simulator ELF
  -> artifact verification
  -> JSONL evidence
```

## Những gì GitHub CI kiểm tra được

Workflow `Gate A.2 - Gemmini Preflight` không build simulator. Nó kiểm tra:

- CHIA commit pin cài/import được;
- cluster YAML parse được bằng chính `chia.cluster.config`;
- worker `gemmini_chipyard` expose `chipyard=1`;
- image Chipyard đúng `ghcr.io/ucb-bar/chia-chisel-build:latest`;
- Verilator và RISC-V worker cho bước sau tồn tại;
- SafetyGate cho phép đúng typed build action;
- upstream `ChiselBuildNode.build` vẫn yêu cầu resource `chipyard=1`;
- `GemminiChiselBuildExecutor` được đánh dấu non-mocked.

Preflight PASS **không đồng nghĩa Gate A.2 PASS**. Nó chỉ chứng minh code/config contract sẵn sàng cho host thật.

## Điều kiện host thật

Host chạy build cần:

1. repo `chia-work` đã clone;
2. `./scripts/bootstrap_chia.sh` đã hoàn thành;
3. Docker daemon hoạt động với user hiện tại;
4. SSH public-key authentication từ host tới chính `THIS_MACHINE` hoạt động không cần tương tác;
5. truy cập được GHCR để lấy các CHIA images;
6. đủ disk/RAM cho image Chipyard và Verilator build.

Không hard-code credential vào repo.

## Preflight host

```bash
./scripts/preflight_gate_a2_host.sh
```

Script sẽ kiểm tra Python 3.10.19, `git/docker/ssh/chia/ray`, Docker daemon, self-SSH, cluster contract và manifest của ba image CHIA. Nó cũng in free disk/RAM để quyết định host có phù hợp hay không.

## Chạy Gate A.2

```bash
./scripts/run_gate_a2_build.sh
```

Có thể giảm/tăng tài nguyên bằng environment variables trong giới hạn SafetyGate:

```bash
MAKE_JOBS=8 BUILD_TIMEOUT_SECONDS=7200 ./scripts/run_gate_a2_build.sh
```

Script tự:

1. chạy host preflight;
2. `chia up configs/chia-gemmini-local.yaml`;
3. submit `scripts/real_gemmini_build.py` bằng CHIA job;
4. lưu job log;
5. kiểm tra JSONL evidence;
6. `chia down` kể cả khi build lỗi.

## PASS condition

Record cuối phải thỏa toàn bộ:

```text
safety_decision == ALLOW
mocked == false
verification == PASS
tool_result.backend == chia-chipyard-chisel-build
tool_result.config == GemminiRocketConfig
tool_result.simulator_binary_size_bytes > 0
tool_result.simulator_binary_sha256 != ""
```

Evidence mặc định:

```text
results/real-gemmini-build.jsonl
logs/gate-a2-gemmini-build.log
```

## Nếu fail

Phân loại theo stage trước khi sửa code:

- `preflight_gate_a2_host.sh` fail: host/Docker/SSH/image access;
- `chia up` fail: cluster provisioning/resource topology;
- SafetyGate != ALLOW: typed-action contract/policy;
- `build_failed`: Chipyard/Chisel/Verilator build;
- result không có simulator bytes: artifact generation/collection;
- job thành công nhưng evidence path không có: Ray job/head-path persistence.

Không chuyển sang Gemini agent hoặc experiment U0–S4 quy mô lớn cho tới khi Gate A.2 PASS.
