Source: https://hackmd.io/@QQ5HFJZeT1-uFJm16Qaq_Q/rJUTYuX4Ml
Captured At: 2026-07-20T12:06:39+08:00
Notes: Authoritative companion sequence diagram for chunked prefill with Mooncake layerwise session and ranged-transfer APIs.

# Chunked Prefill + Layerwise：Mooncake API 完整流程

场景：`use_layerwise=true` + `backend=mooncake`。

```plantuml
@startuml
skinparam shadowing false
skinparam ActivityBackgroundColor #FEFEFE
skinparam ActivityBorderColor #333333

title Chunked Prefill + Layerwise Offload：Mooncake API 完整流程

start

partition "Scheduler（请求一次）" {
  :batch_is_exist(前缀 block keys);
  note right
    PROCESSING 不可见；
    仅 put_end 后可 hit
  end note
  :生成 ReqMeta\n(load_spec / save range);
  :下发给 Worker;
}

while (Worker：还有 chunk?) is (yes)
  :当前 chunk = Ci;

  if (需 load?\n含前 chunk 已 put_end 的 keys) then (yes)
    :batch_get_start(load_keys);
    note right: 每 chunk 可调用；lease 不在此释放
  endif

  if (saving rank?) then (yes)
    :batch_put_start(save_keys,\npage × num_layers);
  endif

  partition "按层流水 L = 0 .. num_layers-1\ncompute L ‖ onload L+1 ‖ offload L-1" {
    fork
      partition "onload L+1" {
        :batch_copy_get\n(src_off = (L+1)·page);
        note right
          Mooncake: batch_get_into_multi_buffer_ranges
          → TE TransferReadRange
        end note
      }
    fork again
      partition "compute L" {
        :Attention(L) on HBM;
        :save_kv_layer(L) 入队;
      }
    fork again
      partition "offload L-1" {
        :batch_copy_put\n(dst_off = (L-1)·page);
        note right
          Mooncake: batch_put_from_multi_buffer_ranges
          → TE TransferWriteRange
        end note
        if (失败?) then (yes)
          :batch_revoke;
        endif
      }
    end fork
  }

  if (Ci 是 last chunk\n且曾 get_start?) then (yes)
    :batch_get_end(load_keys);
    note right: 本 chunk 已知 last；\n最后一次 onload 结束后即可释放
  endif

  if (saving rank?) then (yes)
    :batch_copy_put(末层);
    note right: Mooncake: batch_put_from_multi_buffer_ranges
    :batch_put_end(active_keys);
    note right: 每 chunk 结束 → COMPLETE
  endif

endwhile (no)

:Prefill 结束;
stop
@enduml
```
