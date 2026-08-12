# Mooncake Layerwise Performance Raw Characterization

Single formal attempt with eight concurrency waves; not a statistically significant result.

## Raw Results

| Topology | Input | Output | Variant | Concurrency | Repetition | Input Token Throughput | Request Throughput | TTFT Median | TTFT Max | TTFT P95 | E2EL Median | E2EL Max | E2EL P95 | Achieved Concurrency | Output Token Throughput | TPOT P95 | ITL P95 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dp1 | 16384 | 128 | BULK | 8 | 1 | 4822.33 | 0.2943 | 7646 | 25761.3 | 15912.8 | 25016.1 | 43109.3 | 33275.1 | 7.6167 | 37.6745 | 137.9 | 156.8 |
| dp1 | 16384 | 1 | BULK | 8 | 1 | 5222.15 | 0.3187 | 24990.5 | 25468.6 | 25211.5 | 24990.6 | 25468.7 | 25211.6 | 7.5568 | 0.3187 |  | 0.1 |
| dp1 | 16384 | 128 | LAYERWISE | 8 | 1 | 4568.47 | 0.2788 | 9944.3 | 26895.2 | 16628.2 | 26599.9 | 43457.2 | 33106.3 | 7.5958 | 35.6911 | 132.8 | 144.8 |
| dp1 | 16384 | 1 | LAYERWISE | 8 | 1 | 4942.28 | 0.3017 | 26487.8 | 26748.4 | 26597.2 | 26487.9 | 26748.5 | 26597.4 | 7.5654 | 0.3017 |  | 0.2 |
| dp1 | 16384 | 1 | REUSE3 | 8 | 1 | 3922.47 | 0.2394 | 33254.7 | 34585 | 34166.9 | 33254.8 | 34585.1 | 34167 | 7.5517 | 0.2394 |  | 0.2 |

## Per-Request Results

These rows retain the stable request identity and correctness fields from each formal AISBench details artifact.
Complete prompt and prediction payloads remain in the immutable raw evidence.

| Point | Repetition | Request | Data ID | UUID | Success | Input Tokens | Output Tokens |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |
| dp1-16384-bulk-o128-c8 | 1 | 1 | 1 | 5c3d595096b641d79706995612bf5ea4 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 2 | 0 | 5b3d6cf857f14777b1fbe560493fe02f | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 3 | 2 | e52979ccb2a94204a2f144c4800aebc9 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 4 | 3 | 5a6f18c721354ddfbc40f08d89bd5441 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 5 | 4 | d6c005dd948d49e0bd633617febbd684 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 6 | 5 | 896d9df0e75d46cb9eba0fe46cc391bf | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 7 | 6 | 013442c3f0b14ad58208d838c99d77e7 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 8 | 7 | 810f0c6bf3d84566ae9bdbcc78dd3315 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 9 | 8 | 9e9cc059b6cf4d7d957fd099fdb88ba7 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 10 | 9 | 327b2f4eec7b4443a773309bffa60c20 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 11 | 10 | 22f3783816c744ee93e2c9b0824f13d6 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 12 | 11 | 809bc470196447ae9d6d1f2ee8f64fa8 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 13 | 12 | 8cc73cf473e64a6ca49582dd77ac196e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 14 | 13 | 702ae2e02c764ab5b45012f330d4cc0b | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 15 | 14 | 3d9a96b4eb7b4b00a42cb72ac45dbce6 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 16 | 15 | 6296e313771b4b8abd63dcebc923dca2 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 17 | 16 | 5fbca328f806457daca78f915cd147c4 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 18 | 17 | 10a0c64a4b74422cb22fbf860c6282ce | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 19 | 18 | e1a03607b99b468589aff67e42409d4c | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 20 | 19 | ecd801cf77ee4bc487d11ef729ef44c9 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 21 | 20 | 326777b01c3b4e3f90e3f8858e145805 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 22 | 21 | 97760e3df98144ad97377645e75c12c4 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 23 | 22 | 07651732416a4a6ead9a47cc2cfa378c | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 24 | 23 | 49f41b126b4d487e80ee29e7cbd2fe3d | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 25 | 24 | e2e67e42d7df438cbb5e7d9664355d5f | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 26 | 25 | 51069b080cb348c589d2353c3c79561e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 27 | 26 | 8788ae2be72d452baadbe50892affe41 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 28 | 27 | 519b919c318844fa9adf94d74d921085 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 29 | 28 | 1bef527afbdb445f8c4f8c2c9a140f9e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 30 | 29 | de28e38c34774ba2945cf71c672172ea | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 31 | 30 | a863f0c8334e4d8a8e803a80b0266748 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 32 | 31 | 24904cdf6f07403484e771710d36e7f5 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 33 | 32 | 985140cb987b42189b0851412bdef66e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 34 | 33 | 987770a35f964a78a062e05d8d28a654 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 35 | 34 | 14a67b1c9a234e56a6f041a1693b6a6b | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 36 | 35 | e7b7350eded94a5fbb17d55212c8e0d7 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 37 | 36 | 6e360aba44fc47059e1cc94d3e4c579d | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 38 | 37 | 5a6971abbd2e485a8eb102ee2db9ad9b | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 39 | 38 | d11da7527dea4bbb9710ba662deeaa0e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 40 | 39 | 0781e4ea3172409687f6bcce73d342d0 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 41 | 40 | 5e1130f10d6c4f7094b7ca60590d712c | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 42 | 41 | 7acbed715983483aaa3401efabf9881d | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 43 | 42 | e0c74300453745dd868ffc0dcc5bb2bc | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 44 | 43 | df9c1c934824436c8920d43231ade739 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 45 | 44 | 5f71f2eb9aad4573b3d0e4a933d6a6dd | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 46 | 45 | 9cef26ab485c4e958a047b0d8281dff9 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 47 | 46 | 28e4cc36440446d08f39fd61194db7ab | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 48 | 47 | c0ce457b359d4bfc942c5a0467b67403 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 49 | 48 | 3131e601056e4a5c8cd7891a2c370e0f | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 50 | 49 | b9afb6237a3f4ffd91855f2142c1fb7e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 51 | 50 | 46f163bc37424131850817cf51a5831e | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 52 | 51 | e22d312df0644f159fdcb98d79d18929 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 53 | 52 | d7a365edfae9440e8042179ec489dcb8 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 54 | 53 | eccb867587554b2793e1c5786c8e6149 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 55 | 54 | 84f90ff5382746f49d18622ffe568737 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 56 | 55 | 61bd9384eea144b7badd681ad1a03bfb | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 57 | 56 | a59681d3501e4a87a11230854c82308c | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 58 | 57 | 98b446e8a26849839e40473a0c2fd9e7 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 59 | 58 | 4a32e820a76a4093bb044397d9ef2b3a | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 60 | 59 | 5f7929023a934863b3156d67ccf4ed2f | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 61 | 60 | 42bb227273b448fcadee986b17d293a5 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 62 | 61 | 73cc3a86becf4751a9487a0a4f33f185 | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 63 | 62 | afbab4a0ce3d4e1db93f38184c1a4bad | true | 16384 | 128 |
| dp1-16384-bulk-o128-c8 | 1 | 64 | 63 | 21aed3660c7a48e789ad04de15860ed9 | true | 16384 | 128 |
| dp1-16384-bulk-o1-c8 | 1 | 1 | 0 | 2db87e0ff6444ec9b204a8a1ff052371 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 2 | 1 | 1ebaa8f09faa41319b1bccc5a52aecc0 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 3 | 2 | 03d6d4d00a7f485589b168aa658092ce | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 4 | 3 | c59a3e0c0d1c4e3f9e1e2b775029e599 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 5 | 4 | f2a5db02039845edbc06102b1b896504 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 6 | 5 | f88bb642805941118559e20274ed961e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 7 | 6 | 6cc41d6ee9fe43eb80a5f1fa341faf5a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 8 | 7 | a64dbec674e04fb3819fac5a71ec447f | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 9 | 8 | f8d1bde0ae0d44c1b7d85e6a11b9abc0 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 10 | 9 | 1e025c4e67734a4dbe242ff86f07bbcd | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 11 | 10 | 8d57baebc2554479b70bb997804fd8a9 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 12 | 11 | 057615c1c9464217aa98cf16c84e7359 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 13 | 12 | b160d679da124744aa2d687cc0d27bd8 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 14 | 13 | 326b6651c7884ce2bdf279e3f01c5dea | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 15 | 14 | 7747e417496f4efbbb4306f5a96f4be9 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 16 | 15 | 66f12dfb7c014161a7616a899c70b5ce | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 17 | 16 | 4dac941e54184334a0bf9a837915d1af | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 18 | 17 | 2826f2ffc3e5483199bdf26dcb756e40 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 19 | 18 | 79284b25724f49b3918475c00c48ca7c | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 20 | 19 | 53ea22f698734cbf98cb023b3602ac9b | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 21 | 20 | b2b324b9af9c4ab5932abd4d590a10c9 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 22 | 21 | fa300afe7b894d1a86003ce6243c8381 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 23 | 22 | 938b89a81f5948ea9fb4bf0b528b49a5 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 24 | 23 | 9c4b8d7c3cff444da18b8f6480037a8e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 25 | 24 | 554a9ef14898408cbe1fe3ebe160cfc1 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 26 | 25 | 4b18c160e3ff4b5f8dfc597e56d9a3fd | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 27 | 26 | 9c96af49c9224915b8fbb3169ee33474 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 28 | 27 | 7d6a5e5bf3b540c494abfd3a6206757c | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 29 | 28 | 813310a945904bbf810bdc0dd040e128 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 30 | 29 | acc7498689654d5581948d3e9bc301da | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 31 | 30 | 40b22fed41634dac9e6600c328c595c7 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 32 | 31 | 48a7ec2126eb4dc085aa00de112d7007 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 33 | 32 | 9249677576fd48d9a29bd95187489631 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 34 | 33 | 282cd1243e0f4f7dbca9f72b5a93502f | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 35 | 34 | 0b6bd621e435415c960d357a14163e81 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 36 | 35 | d5f2fd0905814e919fe90882dba1f5e4 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 37 | 36 | 7b7acddaaed649cf902096c80d4a9448 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 38 | 37 | b02de636942c434f8aeadcdde1f2aad0 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 39 | 38 | 037b65503b924deeaa9e4e56feafb4a2 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 40 | 39 | d59a2bbf4c974bc6a555fc13ac8973d9 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 41 | 40 | 103cec0f5fdb4164a33da6887995b4a8 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 42 | 41 | 097c19f68d4445a3bf3c9542d44d46bd | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 43 | 42 | 0464f0ecfcee43bba4f5b9b98c27e22f | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 44 | 43 | db183d8499e4473590c6cd9c7a899fce | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 45 | 44 | d9b07cd76ad44096a9de83fd43282d93 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 46 | 45 | d1ae12300e4d444e890cdd7c7139d299 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 47 | 46 | 7e47900c62c6480584bb5e7602fdcb54 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 48 | 47 | 451d3b095495438b90eec7bb75399482 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 49 | 48 | d499f3fbf3e84440ad1c62432d3efa57 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 50 | 49 | c26ba89a7de34f5fad41622128bd7690 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 51 | 50 | 5d1d93ee06a54c439f460fcb72014288 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 52 | 51 | 767826418e1a45e190194bedbef2b93e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 53 | 52 | 70ace41ebb3547cc8c88c51db44109bc | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 54 | 53 | 938f1c6482684ad7b06ff4c12a269cea | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 55 | 54 | 89fa7b968ee849249ca3fac8536cdd77 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 56 | 55 | e15a256b1c8a4bdcb5d96f6437faf856 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 57 | 56 | 67272f96f37c4bfdbf9bb4dec233522f | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 58 | 57 | bebd23f534c145dc82bf8cd7a7786248 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 59 | 58 | d1e07853164743479282bca909b0dde8 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 60 | 59 | 6aa85435dbe24bdeb7073be3610d9d41 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 61 | 60 | 90b84648ba3549ce86fcb7b79040263a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 62 | 61 | a9b465c3e4624b03af18f41b0443212e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 63 | 62 | e0bf1a79e31542499c3f610ddc7fdb4e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 64 | 63 | ad8cd8cdb4bd4ee2b34525e70bca739e | true | 16384 | 1 |
| dp1-16384-layerwise-o128-c8 | 1 | 1 | 0 | ac20fb519b1a41ecb6dcb879451f7c6f | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 2 | 1 | 0fbed7afabea4abbb7ffec6ba0f8d4bf | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 3 | 2 | a27ad087b01740b280f0fa66a99ff1a5 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 4 | 3 | 4ee17399f390468da796caca57fbb3eb | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 5 | 4 | db00a5f729d84edeb4f6946fbec8435a | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 6 | 5 | 542fe378de374856948283b623c17013 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 7 | 6 | 93af2b51380b4e8585200241c8a2d4d4 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 8 | 7 | f59cadfae571461899e1c8623a221983 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 9 | 8 | 271cd8e353b64695bea1479e32195e22 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 10 | 9 | be62bab3ad7b419a970d8576a0a0704e | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 11 | 10 | 8793f6a063514def972f6ced5b1b75e4 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 12 | 11 | 09035365602e4d6ca313429bcb6965b6 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 13 | 12 | f9c39ab9e52441fe944d7f31e2698b85 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 14 | 13 | c6a67e84f5444b4dbef2232ed5af192c | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 15 | 14 | 141f0c035e274861a5d2fe95840e3640 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 16 | 15 | e849ccfb88e14e5f80ab06e0156c0635 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 17 | 16 | 6b7e586270554937b0d338b0e567cd3b | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 18 | 17 | ed660b04c5914ad198f5937004885fd1 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 19 | 18 | 940992e549794245ba26aa8c2e1ab773 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 20 | 19 | 66e4d0ac322f4ad5a33059fbdf63a6cf | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 21 | 20 | 59754e51a26a404ea973d0e3d96ebe06 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 22 | 21 | d4a03adb5f91483982830eb33697346a | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 23 | 22 | e7419cbeae214a6fb395c515971a9424 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 24 | 23 | fdbb7c818f0745b795a70dff24437f71 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 25 | 24 | 2a1411d4255848db9727ef298e76fada | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 26 | 25 | c64d565a0f2c44fabc79628d604479c2 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 27 | 26 | 29cfc32d23454ffc881bf26709a2ba07 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 28 | 27 | fad1fa463fcd427ea5f82a5e502579ed | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 29 | 28 | 4053ede4ffed4a268e364383f6757b9a | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 30 | 29 | 9fcd7021dadc4f4f802928a507326c83 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 31 | 30 | 14f3cc012ce44792bcc111aabe3785f6 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 32 | 31 | ef4539c33b0f464baba44535d507decd | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 33 | 32 | 910d4bf175924b5ab5954b79cc00a37c | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 34 | 33 | 2c4226e75be64bdc92c848d4f679f4ad | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 35 | 34 | 403927452f8349bdb0dfede81e1ecdc4 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 36 | 35 | 4d26d9a119db4285b5a358bf1ff1fb48 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 37 | 36 | 64fcb57242a3437d98e45728928e751b | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 38 | 37 | 38071be619ba41a2b9be5ede0462da54 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 39 | 38 | 7bfa27a55e0749d889fc1071f277e236 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 40 | 39 | 2c869f55dc1d46fb841ead4b7637a9f1 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 41 | 40 | ea245ea5add64c4da2a1fa78c9906409 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 42 | 41 | 7728385581da4efa9ad574ed9b5988f3 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 43 | 42 | 39712678bebc4b1bab1d36fb5dbb6234 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 44 | 43 | 75fd50346d1d4e1395487da435a82d3c | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 45 | 44 | 3ed3cdcefa8d44fba818a067867e1669 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 46 | 45 | f750ada7abd44ad9be32eb8dfc0d8a71 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 47 | 46 | 8505cf6cf4204d338574ef303521a820 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 48 | 47 | 78dfd388163d43b291b7bf00ab0d7c7c | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 49 | 48 | c5a0ef98f49844449d179de606b6124b | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 50 | 49 | 7d364cf6556f44d7afcba2cbd2d60981 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 51 | 50 | 75f312438eb2413f961f30976fb34d4f | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 52 | 51 | 801483a0ae4c4a18b355466d0b7d9546 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 53 | 52 | 0b8de3a118e943df8e03ee577edffd59 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 54 | 53 | 7c4f9e6ee72847bf8f302a8679278d55 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 55 | 54 | e9b363757c384a1394db9d9836437b95 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 56 | 55 | 69e1f55ecdb547b6805f11f465b4a962 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 57 | 56 | 4ec32bf95720491abbf9b7a18834431d | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 58 | 57 | 4dc8f15de00344958e800cab0c9078c5 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 59 | 58 | 66ecdf834d654cc58be05ed63dbf7fc1 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 60 | 59 | 7ed368d0a72941f4a41aeda2caef7ca8 | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 61 | 60 | a1fbcba9fb204790a029fc82f149b32a | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 62 | 61 | 7d0b0eb8630b41d298a1796e9ebc847f | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 63 | 62 | ecb99f915dec4f9895a9dde2667ef07d | true | 16384 | 128 |
| dp1-16384-layerwise-o128-c8 | 1 | 64 | 63 | 732e74f8ac38419392dba77f3b945f7f | true | 16384 | 128 |
| dp1-16384-layerwise-o1-c8 | 1 | 1 | 0 | c3cab7f40a5b4a24918c8d6b6cdfd552 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 2 | 1 | 96bf9d83a74e4333b563b2afb49e74a2 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 3 | 2 | 3da32ff5319f4b4eb525c038e27bfd80 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 4 | 3 | 444178c05de7445b8acb6abc1e7118eb | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 5 | 4 | 565d041d143347d7bb3be301069fbebe | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 6 | 5 | 85b89d3ef4f349d2b2085bd274de41ec | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 7 | 6 | 8414e6606e754d19a16fe7f081219519 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 8 | 7 | 60b72d808e77445d8dca17887ef592d5 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 9 | 8 | 97c19adfb7344a13b9dcbc6ef2e0a04a | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 10 | 9 | a51c3001b30d4414a6d316916807f517 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 11 | 10 | 3e86b8091ec34aecb9f74043a5131c84 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 12 | 11 | 2b61eff22b2c4061a1e318e79edf61e6 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 13 | 12 | 5361ed65c60e4f779039fafaeb4e90b9 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 14 | 13 | 1219c714941549d0bf248c2dd1cebfef | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 15 | 14 | 11fc6f1f65ec467287e05d60b8039293 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 16 | 15 | a7a633c8de2b41808783e08c7945f80d | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 17 | 16 | b009f506b28b44c488a5cb89b41fdc5d | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 18 | 17 | 4b36474349ef4d9891116d9481af0b45 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 19 | 18 | f3069c465db74bfd9830fcafbb918902 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 20 | 19 | 542917d91d194cf1ba16bbeaa985ee25 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 21 | 20 | 38665531f1794090a78be31835faf600 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 22 | 21 | 6d6540237d3f4dceac0b6e303bd7649a | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 23 | 22 | ba9c90bb61b740ef8b2a166e39ee8e17 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 24 | 23 | 132248c6c3fa4b8ea0cf64b32b1a6d15 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 25 | 24 | 81f90fae6b3e42e893e659e4a38d0082 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 26 | 25 | 2dd802ec950a4a249866fabdf8213651 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 27 | 26 | 22fe8cf17b6b4460b04e91d5e70484de | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 28 | 27 | c359d88549b54a8199f58c147dd4cd7b | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 29 | 28 | 5c71b6961f4945518493ceae9351154b | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 30 | 29 | 474724e8c39c4e35b461ab4dd519ca81 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 31 | 30 | 30f41b4a837d403ab7d9edb35f3bed8a | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 32 | 31 | 7e4ee48a2ee645fbb652062007e035ca | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 33 | 32 | 7fe01bdeb1724d9f90e0201a71a5ae87 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 34 | 33 | acb3d04de21c42458d3bd1195a272af8 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 35 | 34 | b05c3654ec4c4ff5b31e785bec855b97 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 36 | 35 | 7292039c41da4432b2f64f94bdf77030 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 37 | 36 | dc15812f1a0d4e36b17a6ee0527f9f7a | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 38 | 37 | e0e53b4b35c243678dac2d943a030690 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 39 | 38 | 968d36a0402a4fcaa1fefe17ac63bae8 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 40 | 39 | cd0233d490804200b13a0b3d7de75ac1 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 41 | 40 | 8b64e11089b14e33b25638ad32841f98 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 42 | 41 | b0dbe13f48be408d8e7a6afd6fe7d776 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 43 | 42 | 9436d675415b4dceac9e13563c58d289 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 44 | 43 | 3bcb8872d6d44ef09d38a0873a23fe99 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 45 | 44 | 20bb45778880449b8d8d3fca6cd3bdf1 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 46 | 45 | 6a636e4b3d904a498dbc19dcf1ed040c | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 47 | 46 | 93937f9019f24b47ac63f84f3ccdf283 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 48 | 47 | 0d004ff14f514520a4b19a698e7e65cb | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 49 | 48 | 31682a1a123d4f1584c3b197735f960f | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 50 | 49 | 38058c21b9954652a4310e0fda977769 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 51 | 50 | fedf5df1a181468f95dbfeaca71cf85e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 52 | 51 | ec6b53f0e5594c6e91040fc3038cfb14 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 53 | 52 | bdac78e1712b4d18b64fd764159a33a2 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 54 | 53 | b71cfe0cc3ce49499c4182290f6baab4 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 55 | 54 | 7fcc892195e747fb855ec6d355e8646d | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 56 | 55 | 5c8e13d2e4254886bffaf630026bc703 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 57 | 56 | d328f8eb276942c1aa6209c208f7a2a2 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 58 | 57 | 589bc610dd584e0181f466460f26ed3e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 59 | 58 | 2194ef78df934d0cbcb4062e6e6e7259 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 60 | 59 | 2378413784474c38bece1c8cd0e65957 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 61 | 60 | ad0591cd618b4b4f93f4e11a23fc5ddf | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 62 | 61 | fddc42554daa406eacabfd63ecc5ade7 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 63 | 62 | c22aa80f12da40368f60f25c437a91e5 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 64 | 63 | 0b4dadbaf7dc455aab6c3f9bada9f140 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 1 | 0 | 7e649326b5c94d09a54c2e0e6d6df199 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 2 | 1 | 334f2f2d178b4fbc9f67eb4d530b4c4e | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 3 | 2 | b15d4edc600a41e98e309ea2899a54bd | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 4 | 3 | 7a9478c19347479a80d8dbfd3a905231 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 5 | 4 | b4e01ffd87d74e16bfa0e1f9e4cac3e5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 6 | 5 | b9da2e751d1e4eeaa03c3e242f1e569c | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 7 | 6 | 9431505816eb467ea3692bd341a25b18 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 8 | 7 | 0604e665368244809e6aae9363daa057 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 9 | 8 | 1cac10a74e05406eb2a60eab521ff473 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 10 | 9 | 877b1bddc0ab41e1a4d264aea022fab9 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 11 | 10 | e92dc110a6f4423595af61a865d8e942 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 12 | 11 | d6f11792041546829dda883613c228c1 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 13 | 12 | cb5baa2120f74f49be38755dd0ca68c0 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 14 | 13 | 0af146a345314f28b7decbc0e69d1bc3 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 15 | 14 | 0ecc5a8ed0d54cf2bff4142887504103 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 16 | 15 | 6f62ba18824f4fb289061d2128829ade | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 17 | 16 | 390cc2a8f4aa4c418e73d84d0794899a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 18 | 17 | 26dfa0c68f3d4487bf55a9a6da24960d | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 19 | 18 | f2e46ac6d4664ac3be38953d63748eee | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 20 | 19 | 29613d3c74464c18b29b596a94c090de | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 21 | 20 | 1e66bda482ce47f99c58ed6f2aaad6a3 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 22 | 21 | 145eb561f7fd4ebcad18d5892aec9d88 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 23 | 22 | bb1b183e5ade415dacd6d2e47b8e9346 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 24 | 23 | 89a9416b3ccc441c985689b80d43bca2 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 25 | 24 | c9f17d98bd5c4c12b15df8ae161be6b0 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 26 | 25 | 2fb79a96471c4059a365cbda741623e5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 27 | 26 | 3bb93fe05d614aec92aad35cfbe78b37 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 28 | 27 | 3f7ee2a278b04e2ca11f205b7422e39c | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 29 | 28 | 4cf8ca7a4e8b436da62a86c780f71a50 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 30 | 29 | 372e1110ae934acdb3b449180e78de1c | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 31 | 30 | 3e7e8c273bee49cda9606119e52b261d | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 32 | 31 | 0572942d76634680965dc45fb2c2ff88 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 33 | 32 | 9364379d7add44858b7c062fcbddd2e4 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 34 | 33 | f1d6e11157424995b0b5e94519b7a223 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 35 | 34 | 00de6aac04d34e3fab001fea8cbd3ed8 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 36 | 35 | 891cd0f8fabc490fb0edd69eab7edd03 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 37 | 36 | 651857b2267a4d6d8b09768aa4c7a2eb | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 38 | 37 | 9eba177a3acf432b9c895d9ae5134dbe | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 39 | 38 | 889bdaa59cdf4e6abc116503e12e0511 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 40 | 39 | 518673b876c94438ac525b8064a25b21 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 41 | 40 | 205bf87326924dbf8762e563c8a76efe | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 42 | 41 | d2095fecc68a44fb891ada4d599de884 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 43 | 42 | 1259b7a171c6425ab0d5c7efa7a1e3a2 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 44 | 43 | 34dfcbdd9fe942fb8d0e5d2062c72a53 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 45 | 44 | 5612bafa96114a0fbd484289c64da359 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 46 | 45 | f2c5977725d0475a95fd1ab95301ebed | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 47 | 46 | fec6e36669014c9e973373b80733304f | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 48 | 47 | a22c123c68494cda9f36508203ba94fc | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 49 | 48 | 7d1aca3b2cfa4128b078ed5dbd23ee83 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 50 | 49 | 59185b3e7992484692e194c64b02c532 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 51 | 50 | 0a293dcced32453197c78de207a5dd90 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 52 | 51 | 9a42ec60c1a84334a83fb9ee7b944058 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 53 | 52 | eab4345d8e2e48b4b78b97eb96b180ed | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 54 | 53 | b6e67b407c8042b38e7b93266fd12d1a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 55 | 54 | e3f75549233849d59760f35c5e464f06 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 56 | 55 | 51cf6228c78441e7b2f1cbe50192c530 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 57 | 56 | 2146f60e35944c9a9a8961d41340b53b | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 58 | 57 | 376cd4a2c1cd464a8e8051f6bffb2f89 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 59 | 58 | 5a4ea850f3ac49edb8504f11b8732244 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 60 | 59 | c995460858b14aa49bb68702d1b1ca10 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 61 | 60 | 9158e8bb35ba48adb1e324f0ddb81b72 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 62 | 61 | 9371a761fc8749f1ad1e7c3709d5cbd5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 63 | 62 | 65fec2ea10ed4ff3bab73582a0527cb8 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 64 | 63 | 56f3389900c640daa923759d419f96ba | true | 16384 | 1 |

## Direct Ratios

| Comparison | Topology | Input | Output | Concurrency | Repetition | Metric | Ratio |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.946407 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.946658 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.05991 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.05025 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.05496 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.05991 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.05025 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.05497 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 1.00114 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.946658 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 2 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Input Token Throughput | 0.947356 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Request Throughput | 0.947333 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TTFT Median | 1.30059 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TTFT Max | 1.04402 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TTFT P95 | 1.04496 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | E2EL Median | 1.06331 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | E2EL Max | 1.00807 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | E2EL P95 | 0.994927 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Achieved Concurrency | 0.997256 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | Output Token Throughput | 0.947354 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | TPOT P95 | 0.963017 |
| LAYERWISE / BULK | dp1 | 16384 | 128 | 8 | 1 | ITL P95 | 0.923469 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.793655 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.793503 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.25547 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.29297 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.28461 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.25547 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.29297 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.2846 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 0.998189 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.793503 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 1 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.751121 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.751177 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.33069 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.35795 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.35521 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.33069 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.35795 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.35521 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 0.999325 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.751177 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 2 |
