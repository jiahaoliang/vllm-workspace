# Mooncake Layerwise Performance Raw Characterization

Single formal attempt with eight concurrency waves; not a statistically significant result.

## Raw Results

| Topology | Input | Output | Variant | Concurrency | Repetition | Input Token Throughput | Request Throughput | TTFT Median | TTFT Max | TTFT P95 | E2EL Median | E2EL Max | E2EL P95 | Achieved Concurrency | Output Token Throughput | TPOT P95 | ITL P95 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dp1 | 16384 | 128 | BULK | 8 | 1 | 5620.26 | 0.343 | 3480.2 | 21737.6 | 13335.8 | 21076.8 | 39531.1 | 31086.9 | 7.6277 | 43.9083 | 142.2 | 146.9 |
| dp1 | 16384 | 1 | BULK | 8 | 1 | 6233.78 | 0.3805 | 20956.8 | 21348.2 | 21168.2 | 20956.9 | 21348.2 | 21168.3 | 7.5656 | 0.3805 |  | 0.2 |
| dp1 | 16384 | 128 | LAYERWISE | 8 | 1 | 3828.68 | 0.2337 | 15113.4 | 32745.6 | 20050.2 | 31925.3 | 49649.4 | 37244 | 7.5857 | 29.9116 | 135.5 | 145.1 |
| dp1 | 16384 | 1 | LAYERWISE | 8 | 1 | 4063.7 | 0.248 | 31971.9 | 33175.7 | 33097.9 | 31972 | 33175.8 | 33098.1 | 7.5683 | 0.248 |  | 0.2 |
| dp1 | 16384 | 1 | REUSE3 | 8 | 1 | 3946.37 | 0.2409 | 32991.7 | 34383.3 | 34351.5 | 32991.8 | 34383.4 | 34351.6 | 7.5593 | 0.2409 |  | 0.2 |

## Per-Request Results

These rows retain the stable request identity and correctness fields from each formal AISBench details artifact.
Complete prompt and prediction payloads remain in the immutable raw evidence.

| Point | Repetition | Request | Data ID | UUID | Success | Input Tokens | Output Tokens |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |
| dp1-16384-bulk-o128-c8 | 1 | 1 | 0 | 755afa11d3f74e7686aa4e74214466dc | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 2 | 1 | 3d922b489c1b45b98ebccfd4fa25d871 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 3 | 2 | 1c6309cd2d2344648ccf00c569b1b4de | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 4 | 3 | cd085d7c2854409bbc4a17abf36f5d8d | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 5 | 4 | ae2478c131014f12bc381b39a2b9251c | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 6 | 5 | 4a2f622dcabf49e8afbd11d4796fffd9 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 7 | 6 | 08c483c624cc48ae9a56629321f78085 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 8 | 7 | c4c3ee991ed048ec98bfb0ad91068b26 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 9 | 8 | 013ea6f1c3444dd3a0be74268ec819ec | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 10 | 9 | 9cb275de155a4f78b5dd2cf1598e60b2 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 11 | 10 | 916caf071373497fa7956914a2d60ac8 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 12 | 11 | 22d19b37bb3f4b20b5088a39211ec302 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 13 | 12 | 32e1a18389154891b4cf992a9f30a7a1 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 14 | 13 | b2f314f1c0a04cb5b9c824830453e5ba | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 15 | 14 | 56e1ec450086446890e79113907eac87 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 16 | 15 | 841ef37efe3241a583760a67b2e91e1a | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 17 | 16 | 41fb04115125426089201308448a967e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 18 | 17 | 882e2a7602a1412d9dae7d6fa1c088cc | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 19 | 18 | 71930f5626364f31b2e1640f08ec52e8 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 20 | 19 | 38dad01cdcdb4e99b18e10c2b6315892 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 21 | 20 | 643a2e6bac3a487a95d7a26ff8add270 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 22 | 21 | d685c5915a9348aab15d008a428aa984 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 23 | 22 | feeeb850435841189cf0058aae4520b0 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 24 | 23 | 5d231dbc425446b18b21d8640807aa2c | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 25 | 24 | cb3651702eae44659fb17d33de7c4b1f | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 26 | 25 | 5d1f247aa12f45708a5399e569d4594c | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 27 | 26 | a21ef64f970f4afe824e66c7464577ee | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 28 | 27 | 730b1f24f4b54d648b749117a8d63125 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 29 | 28 | 35dd65e91c884104a81eab1e35e60d2b | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 30 | 29 | 6c9f771140054a2d8f3adc6e7a1fc28e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 31 | 30 | 13f10037a85b4fc88ac9bc2b3f493ca7 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 32 | 31 | cdae14174acd42889cecbb110974bd64 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 33 | 32 | 9e60ddbe9dfd4da89f80737a5753ecec | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 34 | 33 | 2ee9a113939c495fa835c853c0d4d7e8 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 35 | 34 | 4bb60ecbddb24eba95e3b0cbee066b37 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 36 | 35 | cf247121f2e24cac97e3468bd62fd260 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 37 | 36 | 8e971105efea489ebec80dca957a709a | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 38 | 37 | 51f98913f0ce45b19a19a5f0a103890a | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 39 | 38 | f7310d78d8fa4c84a3663d6fa13116ac | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 40 | 39 | 810e0105dc0b4e1b95ca0dbf79e1eb9e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 41 | 40 | 0c2c7cd88e8e4e72842883919e594788 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 42 | 41 | 5c02dcf8a6fa4dec919cf24047e68166 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 43 | 42 | 684c53cd82d348f0afb5a681a66f3ad0 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 44 | 43 | 08f523f1a29945a5affc3bc139f50b2b | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 45 | 44 | 58361693a1a64fca8b73327a3827c78e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 46 | 45 | 88e4866c649f443aa1192846351e39c1 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 47 | 46 | 6fc416a4f8314ae89fff57defe179ec8 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 48 | 47 | e37c59f0306d4fb6a3162c392d86f2e3 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 49 | 48 | a1b909ab835d495baa023268ac9ceadc | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 50 | 49 | 61387dff648647b4951cb7f59bfe9d44 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 51 | 50 | 4086ff7b87b1432496dcf211ba927725 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 52 | 51 | fc5e56f2318e48f3a6574f4bceb2d314 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 53 | 52 | 74c43b8979f044d1af14f3018eb50e9b | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 54 | 53 | 5ab10c3581544ecfa8c59b8b50049a44 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 55 | 54 | 8f24f29e333e484dac24c61990077db3 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 56 | 55 | 8a5621ef785240b6bb2b6c432de169f6 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 57 | 56 | 3ed043c295cf4597a4914accba01dd71 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 58 | 57 | ef9d72ee4d2e4912bc1998f9d9369d1a | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 59 | 58 | 29f2e94af77640f8bf36c85efd295763 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 60 | 59 | 4a5c6010f4ba4e86b091f8c58964be39 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 61 | 60 | ad0170ea4782482b890244d6e313ed03 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 62 | 61 | 6afd0ddf37824b7eb8d073550bdbb786 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 63 | 62 | 5edb21a3ada4447e830f8abd116e940b | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 64 | 63 | 3c1a7004492c4d05b2c28f6fda8d40af | true | 16384 | 128 |
| dp1-16384-bulk-o1-c8 | 1 | 1 | 1 | 45733493a0bc4c05a004f4aec21fd24d | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 2 | 0 | afd663f0fa434fb483cb678090265971 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 3 | 2 | 1497ef6bbd914b068300ad3ea3fbdd54 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 4 | 3 | f4bfcc80307c41deb88553eb46aa012a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 5 | 4 | fa67176c2f9e47f8b67ebff7ef30464e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 6 | 5 | 2dd03954029a4295a9aa1ec3bf779dbc | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 7 | 6 | 713283341daf4d108ff753fbdedf9f49 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 8 | 7 | 8b1267986d774ca9a18770d6152ae976 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 9 | 8 | 3a04d6c79437417c99113b1abf6843f0 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 10 | 9 | 90834d106c074561b4c4c11948879b19 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 11 | 10 | 210829ea9c314b64a754aabe4d4015ff | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 12 | 11 | f6a71ab7c3b64095bcb4a7e1daf0cfa2 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 13 | 12 | 7bae92dc2ea54fb3b501f7da6dc67b02 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 14 | 13 | 1478c53ca4824b9eb9563a601b371c43 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 15 | 14 | 6f50b397537b48e4988ca5791cd963e8 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 16 | 15 | b35a7e3f44e24b7cb56744ab441dacaa | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 17 | 16 | 1aaae59a6dd447e9ba0edbff94136b58 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 18 | 17 | e2bc8c8fd46c42458bea00453b08be19 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 19 | 18 | 231e15aa2dde4702bd7aec207c53ef3c | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 20 | 19 | 204a0278af424e4bbdd5f17d736c109d | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 21 | 20 | 629ca46a5d1640db82565b1081482c19 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 22 | 21 | 3358cd087dc9439dbff58abffe229bfd | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 23 | 22 | 80f0a8302f8c4ee89937e8f731a51d1c | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 24 | 23 | 8329e8f3d8034d5b87d4a0f82de43161 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 25 | 24 | 8d75362c1a2a4294a48f6d6779218f52 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 26 | 25 | a22160644c7e46afb1fcc4a658ef9496 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 27 | 26 | 93ef44eeb1374c0a92dd67a0499f44b4 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 28 | 27 | 2f032e80b07f4db8897b2e26caa6a506 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 29 | 28 | 0f67898c62c2439fa5db16231dfc05e6 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 30 | 29 | 204124592f2f4819ace211cf3fc370e5 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 31 | 30 | df2cbd47f1bb430ca52eca18e8e5bf0a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 32 | 31 | 430e1283ec5c40bfba68eb0f039d95a6 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 33 | 32 | f790bb37feb042a8ba9512b3d5081cb7 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 34 | 33 | 7e6610e081074ae9a149cee76e009ae1 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 35 | 34 | d85b67d88cfd4d0fbcf40bb52126fab4 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 36 | 35 | 82e3ae48db1b421ab1905ad6f734e54b | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 37 | 36 | a80479568fda46f290e76a5e50a64d8a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 38 | 37 | 80e27b00918242ddb94ec12b0d2d0d08 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 39 | 38 | 6f92736ac2c04b8195a8b54e74d42439 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 40 | 39 | 2a6a1398c2454575886d4e58e951c573 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 41 | 40 | ff0ff94f64ca4dd9859fd404c3ed1512 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 42 | 41 | 1510b720c4604a5b875c2c8852acc204 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 43 | 42 | 93cd97f92a1d44129aafcd5fa1923b8a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 44 | 43 | fa69e9cbeb7e47f092a2caa7d374a2ac | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 45 | 44 | e8ec56e68a4e4977ad9c8f7c7e890c77 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 46 | 45 | 85d8249dacb14c8c8acf83da765169ab | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 47 | 46 | cd2cf0ba1ab4441f9461287312b39cec | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 48 | 47 | 618b4babfb144574b89c633d40cbfb93 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 49 | 48 | 79580dadc9484807a9f4455c7f87d09d | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 50 | 49 | 130a3b8ebfb740819df2436983df5b1e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 51 | 50 | 0be4de97b2ec42b887f21a4b42e61d53 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 52 | 51 | fe68ffde34a1476db553d9fd246cc2c2 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 53 | 52 | 691d4d50ff6d44afaf59e5ce6d4b4819 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 54 | 53 | 5dbd5b74ffb2478aa8abb5f0e1ea7493 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 55 | 54 | cd63495829fc4633b3b854cf5f8b3a12 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 56 | 55 | 409af2ea6f2a44a6b97f6af15ff46b62 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 57 | 56 | 8f3d614febea49d8b779c54495850527 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 58 | 57 | 3c4f124875b841b892f8b2748a7868ba | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 59 | 58 | 69baced56f5c4efa93d4c544784da186 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 60 | 59 | fd8657ac1e864ac4bf8a5235c5653acc | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 61 | 60 | bb07d7d36d4b4a8e8f4aed36b569c98e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 62 | 61 | fd1e12dce204491f81761d2d1493c1e2 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 63 | 62 | 054955ad9ee3423e84382b8e01829fea | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 64 | 63 | 502aff991b224cd5ac945c94e603decc | true | 16384 | 1 |
| dp1-16384-layerwise-o128-c8 | 1 | 1 | 0 | 54a99a6695164fe2a23d5514fc9e7a47 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 2 | 1 | fed80aa88ae649a38e4ef808f644e9b6 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 3 | 2 | 8924cb61c4574e86bd9a2ed84a0b6b87 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 4 | 3 | a31c57d8a3ec4546ba90f21d794e5aba | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 5 | 4 | 653a53d61881404dadaccc5523931a34 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 6 | 5 | 0818a4d5171442dca5b5461163f37ac6 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 7 | 6 | 149d1e00347a4bc7bcc4e5adfb2ed22a | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 8 | 7 | 3d2c591cf7f4424c8efc48000502766a | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 9 | 8 | 01645f0560164544b1bc556ac8ebe430 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 10 | 9 | 234ebea54d704486ae45ec2e977aa9a5 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 11 | 10 | 299374a5a82246d88863d213976679cc | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 12 | 11 | f11e3caf04464a4b8884f83684d57553 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 13 | 12 | 8cf0eddab03d40cfb3777103c5efdfac | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 14 | 13 | a9e2fb663a704b4f9d1c73035b4fc163 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 15 | 14 | 405104cf6be84c6e8bb1b10bf1c30012 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 16 | 15 | 2262b9b6846848c0adec59433252814e | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 17 | 16 | 054cc946c7f24cd29f650bebd0926cb8 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 18 | 17 | 9f6011bc5c0547be8624905c00884f22 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 19 | 18 | 68142b0bdc2a46cdbd2bbbddcbf9681f | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 20 | 19 | 11d9557ab6384e38836c67fac7d79bc5 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 21 | 20 | f3f4f4171bf1406a8001c8ce18c96485 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 22 | 21 | 24a582df21b84b17a1c9b846efeb67af | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 23 | 22 | a2416be17734428a9e5008bd15a56c1b | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 24 | 23 | b593bc4419de4dfbbcd1b488af39ee71 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 25 | 24 | 8824f3a515aa4f749482f9ec14e63c23 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 26 | 25 | 3b91c52e86c24c259dd2571bbfb64bb2 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 27 | 26 | a228ceefcc77465fa03887262ebc8f6c | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 28 | 27 | 7ab86ca79942416282b9c999dba1d36c | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 29 | 28 | f2cb1a26d49242e9b544e6c84aa7a1fe | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 30 | 29 | fb39dd225b8949daae4347c3de10c470 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 31 | 30 | ac962503ef2d4a7f94eb177f5158e218 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 32 | 31 | 3182d0f4fbb549fcb52799e9c4323863 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 33 | 32 | 7c02b7e647f642dcbaed6810725fc261 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 34 | 33 | 614e16eb0fe64119ac7ffc55cb536f63 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 35 | 34 | 0a38f2cf0abf4172a89ef6cf75e07b6f | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 36 | 35 | 9b135421725e42cd99f8a57334abeca3 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 37 | 36 | 14b4cf61d4a343848b6655b56c23756a | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 38 | 37 | f2f04da7d29d4973ba388118667c1043 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 39 | 38 | 64ad5fa3efa94847bc79e6ebbac1ff41 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 40 | 39 | b8b9893ee1604144a55a30f77a8dcf97 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 41 | 40 | 891a9570f84a475694b3831fce7635fc | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 42 | 41 | 3e660fae6e444afe8dec696319dcfac7 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 43 | 42 | 0a38e365d85242528a3e31a1a66c58ff | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 44 | 43 | f94987dd1d254036b25c9e2065807428 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 45 | 44 | 977bb6432cac4d21bc67bdc7f35643e5 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 46 | 45 | f8452add20b043288bec080da417c85e | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 47 | 46 | 7564a5068ddf4531a099be4df6536d1d | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 48 | 47 | f55e567049e64dacaec94d9b528f88a7 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 49 | 48 | 6332d0467092486bbffef66c183c1c76 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 50 | 49 | 1f35db5630ee4dfab254da734d951d6b | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 51 | 50 | 06a865e90acf446d8ff45fc1deb9cef0 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 52 | 51 | 783d3464dfaf4fa4aedad6362a64c23a | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 53 | 52 | 0e0c0682f32a4802bff68f160bc515c9 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 54 | 53 | 5e34c62ac25f429d85f67f2ed73343e8 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 55 | 54 | 1147d46706464d24b651bcd6a50c148e | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 56 | 55 | 5d590c1695b4485fb42ff1981e010d33 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 57 | 56 | 140e21541cac4966b81e1532b8827891 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 58 | 57 | 92913af471b9492c96695796a3aeaed9 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 59 | 58 | c018ecd3251048bfad2425323fa07cd8 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 60 | 59 | 3169878a727949e29594e24548d93f3e | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 61 | 60 | daf147ff936d43dd914e8e8cb0a62fcb | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 62 | 61 | b1850162844b48cda68175aaf1b1a7dd | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 63 | 62 | 461ee254be7d493bab1264ff98c27c4d | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 64 | 63 | c89bde7e87994d929dd8853380c3a7c8 | true | 16384 | 128 |
| dp1-16384-layerwise-o1-c8 | 1 | 1 | 0 | 7739553e773044d9bbff0c9459f432b6 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 2 | 1 | c2f34013e1c0408c8b188ef85ce6aa8c | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 3 | 2 | 6103a0a3e4f74ba68cf96f8aa7df9f28 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 4 | 3 | 9588b2342e5d4673a39e23372860dafd | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 5 | 4 | b3b8903e7cb44e01bf2134c4df1220dd | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 6 | 5 | 9439cf4d67ce4da6b7f862ab575e4f60 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 7 | 6 | 65d730f8695b4dfcaaab25074d5aa16c | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 8 | 7 | 057c4667235740c598a45c93dd5a2f3e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 9 | 8 | 1b0e70046710475683221a9219aa7a79 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 10 | 9 | 7b0e6836c8a94438aaa02c6c071fb581 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 11 | 10 | 4b949b35523243018d556da72186579d | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 12 | 11 | 4bcdd3567db5423e8b136e5b02a58b36 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 13 | 12 | 5cdbd7c3408246ec91c0ccca9333c9d8 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 14 | 13 | 081b69dfd86c4e94aa56c1bd4b19fd29 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 15 | 14 | 8a1a34e5123a42a79d3a6241e025b808 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 16 | 15 | a66a1bbe92c648d5b2f8fc9be65df54c | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 17 | 16 | 1255345f29864ebda625ad3712a5c50f | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 18 | 17 | 1e44e5e0e6434253bf416f4ac97ee25b | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 19 | 18 | 9738ace0e8c84ff784ae7d10f9e8563c | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 20 | 19 | 39ee5f2ee8e344f9ab3fd099e3a0e398 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 21 | 20 | d41769e622c44f948c234011c68a33e0 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 22 | 21 | 52721baff95448d9973492bd8e1cc724 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 23 | 22 | 2df62de4c6624428a1e95a8e96c3268e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 24 | 23 | 937a1a431f204fc1a1245f0b3127b632 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 25 | 24 | ceb1145711704efb8df52646a60006b9 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 26 | 25 | d68e46618d3d498fa0a5d202a34977fe | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 27 | 26 | ff1eb32a3adb42f3a30df0c1510e0aee | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 28 | 27 | 2b22a1b602af44c29b7320e4e5ce6331 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 29 | 28 | 4c5cdee8d41840b789b0721747f5036d | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 30 | 29 | 03c582104d13447ebb5cbaf7e20eccde | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 31 | 30 | f23ab8cb67104b67b8c7c427604d3004 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 32 | 31 | eb600086c4be43d3a64ef907ac7398f1 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 33 | 32 | d3f73056993141d4915220cb4d80c741 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 34 | 33 | 279d565dd89145bd9c359759c30f7c3d | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 35 | 34 | 7bbb8bf13ee34a55bbed2d79b9b3d0f2 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 36 | 35 | b9de3e77a24b42e298ecf50b2699e0ac | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 37 | 36 | f29f305ef978402db25305850c19b063 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 38 | 37 | 431e745de4084e0d90bf44171898b5bc | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 39 | 38 | e43cbfae84e249ce9c23c9105d249ed0 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 40 | 39 | b2e13927ad864f5988d8ba8ea00dce58 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 41 | 40 | 8e0996229a84495eb25c0894567320ed | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 42 | 41 | ea21f4427bd1401aa881061c122198d9 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 43 | 42 | 76ce0057abc843639684d1c6ff9c966e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 44 | 43 | 6c57858d74a94e6d8c1cfaab4567c66a | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 45 | 44 | 8ddb4afb81bb429691a6315d0b95b1a8 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 46 | 45 | 437a743d87134b4083bad477b85e38a5 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 47 | 46 | e6ec9a474d6447479d93134150ef5d41 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 48 | 47 | 0c51ed894b9940ad85a6582192d9f59e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 49 | 48 | 8c0ed99ca24c48998a93483f8d1a59e4 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 50 | 49 | e1d50d2adeb44e578f9f2bb703cb0bd7 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 51 | 50 | fb55a9748452436187ce7718ddc4019e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 52 | 51 | be4dcc19b83d4739b3405983166033ce | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 53 | 52 | 8f64e906621940eb984b6999737050bb | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 54 | 53 | 7ad47cf1ac04448ab4d6bdab03763485 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 55 | 54 | 738bb5985b224b609cb0b3618f37048e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 56 | 55 | 68a29f3cfb254078ae05bf1f591f24a7 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 57 | 56 | 4975eee4033e4a2caa1c9f7f4fa2b834 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 58 | 57 | 99c06a3f07a14978b88f4ac542137599 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 59 | 58 | 8a14e48704254c40a49d38c86c86cbcc | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 60 | 59 | de34c69e06354d79b6302328f9e11424 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 61 | 60 | 91d43fe8711542f9981055a2432f5c5a | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 62 | 61 | dc7be415dd564739a133bb408c934916 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 63 | 62 | 398d59165b704e269eac32ca2862c4c5 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 64 | 63 | 5cf0a9e3cc1f4bba8ae8b2de0ee5112a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 1 | 0 | 075171d564924a1ab226a7779993dbf0 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 2 | 1 | 83f1c991df7e46f385828b467fb4fa60 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 3 | 2 | a1ed95777cf64acb94636f427852e5fc | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 4 | 3 | 93099c74b8e242ce84732915f8edd29e | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 5 | 4 | 49fc9c27c98848aeadecdfd8cf2df575 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 6 | 5 | 47826c979c7c47718ae1cf2d7d87c78a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 7 | 6 | f09bcd9c7c57477bb43667747a9c9439 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 8 | 7 | fa1b2ffbbec54c2f9225010e123c6c07 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 9 | 8 | f21d6c3b42fa4caba58d5d077c7f19b4 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 10 | 9 | 94ac120924ec47ec9d95ab56c3b55f86 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 11 | 10 | 00e5b2e543c94d4e85a5027f6fadcca5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 12 | 11 | c12a4fc3c3ce4029ba78b8f1f64a0b66 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 13 | 12 | 9d789c7fabee4658b66debd6b4183e2e | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 14 | 13 | 78159bc3c6e44206b2bd6f47198db6d1 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 15 | 14 | 6eef26fbb0a44f2c9dc033b66d0b2c9f | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 16 | 15 | f585a751729e486682a3e7353bd7c735 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 17 | 16 | 0d9cff5b21614b649cbddc47f7ea03fb | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 18 | 17 | 109b560b2dfd42fcb98754910c2c6244 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 19 | 18 | 1402fb448b404b00bc2facef208c9e8a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 20 | 19 | 0a3d168554ed43139032e28e9105b6c2 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 21 | 20 | 1c68b57c120a4ed2978c34ba6856db7d | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 22 | 21 | 5e404745470843aba76b7dbe721349a5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 23 | 22 | 140a0d1037244ecd8a488a3d2455a378 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 24 | 23 | ae112513d9784ac9b13cb5dcbf3669cd | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 25 | 24 | 7d04bf6f5e4d4001bc743973e46cb2c4 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 26 | 25 | 8b91bc2bd3f34daf81dea549e2f15b82 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 27 | 26 | 499889b2a3df47beb81c02d6c3897798 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 28 | 27 | e5bb520db2b94e59b398ae0a86035f7a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 29 | 28 | 3f753487cf524fba84eafee8daf7998c | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 30 | 29 | aa712efc404c4d39a5adad348de6fa38 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 31 | 30 | 4cdd5e41797d497a9d1490fdc42dd2bd | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 32 | 31 | 64aa0b0ae33f4c6da3daa283a67d7408 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 33 | 32 | 3489a38d94bb42259640512fb05f0688 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 34 | 33 | 2fdadf43580b4e72a1d8c9cf6e538868 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 35 | 34 | 209d06f739694e2fa336009c4b85e1cd | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 36 | 35 | df35f113bb1241e7b95a909463bc60d5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 37 | 36 | b59f9a3e7295419b876231f20c48c800 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 38 | 37 | 009c802e5add4799a341d30e0d4e4ea8 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 39 | 38 | 6886f5c62f784330a773ae432f9d77c4 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 40 | 39 | c17c76ceec8e46189b993bfb3dea4f9e | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 41 | 40 | fd594ea549ce47b383d7ca67428cd5d5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 42 | 41 | 5559522c29ce4bceb978cf9109eaf350 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 43 | 42 | 602c6e0eebe44ff29cda697449503c5b | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 44 | 43 | 160e3f1e6b40450e88411b7ecda9ff1a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 45 | 44 | 5afe2c25f0df45b6b955686f291e8fdb | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 46 | 45 | e03dc06e5e54487ea72cbd52f779462a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 47 | 46 | 0e05760f964d4fc3a5f4c74d3c9e1d32 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 48 | 47 | d275bbfbe7e141c7860df7fea87e280c | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 49 | 48 | a1c2319b512745c78f8f3fb14cf6aff0 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 50 | 49 | 0a985d902fab42bc8cd7f0fdc4ecab67 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 51 | 50 | 41114fb90eb14806883c4e9130174968 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 52 | 51 | 1281e052c15e44c3b440f78340113afa | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 53 | 52 | ba26fb627a064986a0219e1d3ecf3af5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 54 | 53 | 96ec6a1f83174d5b8d73e98f672e339a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 55 | 54 | 34f897f61f1f4ee2869de2d789294e03 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 56 | 55 | f8e204e6ec9241339ec479bfdd6dac57 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 57 | 56 | 570c6d5ecc2342a9b9f8175fcb194f08 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 58 | 57 | aedbdcb7d32c4de98dedaef6cd4c841f | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 59 | 58 | 103f08b02dbb4812bad126ab20be6500 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 60 | 59 | 29a219ae53cf4995a7beeaec50c33f99 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 61 | 60 | 8b8ae9e04b97459183f2cc302875bfcc | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 62 | 61 | e8b42b2a5e7645229a0abdc186306b93 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 63 | 62 | ed73675e4756417e85e981c5473a8dec | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 64 | 63 | 50b932c52db74bb8a16ba4210570e03d | true | 16384 | 1 |

## Direct Ratios

| Comparison | Topology | Input | Output | Concurrency | Repetition | Metric | Ratio |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.651883 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.651774 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.52561 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.55403 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.56357 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.52561 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.55403 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.56357 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 1.00036 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.651774 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 1 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Input Token Throughput | 0.681229 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Request Throughput | 0.681341 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TTFT Median | 4.34268 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TTFT Max | 1.5064 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TTFT P95 | 1.50349 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | E2EL Median | 1.51471 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | E2EL Max | 1.25596 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | E2EL P95 | 1.19806 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Achieved Concurrency | 0.994494 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Output Token Throughput | 0.681229 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TPOT P95 | 0.952883 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | ITL P95 | 0.987747 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.971128 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.971371 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.0319 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.0364 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.03788 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.0319 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.0364 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.03787 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 0.998811 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.971371 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 1 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.633061 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.633114 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.57427 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.61059 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.62279 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.57427 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.6106 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.62279 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 0.999167 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.633114 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 1 |
