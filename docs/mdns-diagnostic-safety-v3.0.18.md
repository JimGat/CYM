# Clock mDNS diagnostic/safety candidate v3.0.18

This is a failure-safety and diagnostic cycle, NOT a deterministic headroom repair
or hardware acceptance. Console, pins, display buffers, partition/NVS, SD clock,
codec/I2S, RF-HAT and AP/Client/GPS/RTC policy are unchanged. Both layouts and
no-PSRAM policy remain intact. Classic CYD/HackerBox still show mDNS: Disabled.

## Safety change

Hash-pinned build-local service, responder and allocation-helper replacement
translation units never patch managed SDK/component files in place. Responder
binary-semaphore OOM releases AND invalidates partial ownership. Free checks NULL
before dereference. Init preserves responder/netif/timer/service-start errors.
Queue/mutex/stack OOM is ESP_ERR_NO_MEM. Failed static task creation stays ESP_FAIL:
the internal static TCB has no new heap allocation, so this is not observed TCB OOM.
Stop admission, producer quiescence, timeout retention and drain are preserved.
Essential NTP starts before optional discovery. Later hostname/service allocation
cannot finance the preceding stack request.

## USB operator procedure

Use the accepted primary USB-C console, 115200 8N1. No UART/config changes.
Physical reconnect/reboot qualification is separate from native tests.

1. Send `debug status`: expect an explicit current persisted ON/OFF status reply.
2. Send `debug on`: expect ON/persisted reply and immediate diagnostics.
3. Open Universal Clock, choose AP NTP and start. Repeat separately in Client NTP.
   NTP starts first. Debug ON emits lines with these shapes (heap values are LIVE,
   not promised numbers):

       mDNS boundary stage=responder-data phase=before bytes=36 rc=ESP_OK (0) internal free=<live> largest=<live>
       mDNS boundary stage=responder-semaphore phase=before bytes=0 rc=ESP_OK (0) internal free=<live> largest=<live>
       mDNS boundary stage=action-queue phase=before bytes=<payload> rc=ESP_OK (0) internal free=<live> largest=<live>
       mDNS boundary stage=service-mutex phase=before bytes=0 rc=ESP_OK (0) internal free=<live> largest=<live>
       mDNS boundary stage=timer-create phase=before bytes=0 rc=ESP_OK (0) internal free=<live> largest=<live>
       mDNS boundary stage=stack phase=before bytes=4096 rc=ESP_OK (0) internal free=<live> largest=<live>

   Each reached before boundary has an after boundary with the operation result.
   Stack OOM: stage=stack phase=after bytes=4096 rc=ESP_ERR_NO_MEM (257 / 0x101 on IDF).
   No static-tcb-task-create follows for that attempt. UI: mDNS: Resource failure;
   required NTP is independent. Success reaches static-tcb-task-create, then
   hostname/service registration. Generic data-malloc/calloc/strdup/strndup
   boundaries cover actual data requests, including later registration payloads.
   Physical discovery still needs external hostname resolution/service browse.
4. Stop/Home and reenter. Check cleanup/retry and direct-IP UDP/123 even when
   discovery fails. Timed-out producer ownership is retained, never freed live.
   Repeat AP/Client in both layouts, plus GPS/RTC display-only controls.
5. Send `debug off`, then `debug status`: expect explicit OFF/persisted replies.
   Repeat entry/exit: no allocation-boundary heap sampling or logging while OFF.
   Essential errors and explicit command replies remain permitted.
6. Classic/HackerBox controls must say Disabled, not Failed.

bytes=0 for opaque controls/timer/netif means unknown size, NOT zero allocation.
Queue bytes is pointer payload, not RTOS overhead. static-tcb-task-create bytes
is static TCB type size, NOT a new heap allocation. timer-start/netif-init are
operation envelopes, not attribution of every SDK allocation. timer-create is
immediately around actual creation. Before-phase ESP_OK is an annotation, not
proof the allocation succeeds. Clock `mdns_init post-return/post-unwind` is after
init returns, possibly after cleanup; it is NOT the stack-boundary measurement.

## Evidence limits and OPEN requirement

Target responder36 versus native64-bit responder72 is explicit. Host regression
executes generated production init/free/responders/memory helpers/timer-start and
the application diagnostic hook with ASan/UBSan. SDK scheduler/netif/PCB, RTOS costs
and fragmented allocation are modeled. Not a device heap reconstruction, physical
UDP/123 or discovery proof, entered-event/RX concurrency qualification, cache/ROM
certification, repeated physical recovery or no-PSRAM hardware acceptance.

4096 INTERNAL|8BIT must still be allocatable AFTER NTP and internal controls.
Recorded4902 free/3072 largest is insufficient despite PSRAM. No placement switch,
external/smaller stack, static reservation, service removal or speculative reclaim
is included. Headroom stays OPEN. No flashing/publication is part of this handoff.
