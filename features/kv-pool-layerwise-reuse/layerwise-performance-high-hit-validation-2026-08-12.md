# Mooncake Layerwise Performance Raw Characterization

Single formal attempt with eight concurrency waves; not a statistically significant result.
All formal requests passed the frozen 13,312/16,384-token external Prefix KV hit contract (81.25%).

## Raw Results

| Topology | Input | Output | Variant | Concurrency | Repetition | Input Token Throughput | Request Throughput | TTFT Median | TTFT Max | TTFT P95 | E2EL Median | E2EL Max | E2EL P95 | Achieved Concurrency | Output Token Throughput | TPOT P95 | ITL P95 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dp1 | 16384 | 1 | BULK | 8 | 1 | 25355.1 | 1.5476 | 5042.3 | 5592.4 | 5359.9 | 5042.3 | 5592.6 | 5360 | 7.5499 | 1.5476 |  | 0.2 |
| dp1 | 16384 | 1 | LAYERWISE | 8 | 1 | 19245.8 | 1.1747 | 6717.6 | 7183.1 | 6975.1 | 6717.7 | 7183.2 | 6975.3 | 7.5689 | 1.1747 |  | 0.2 |
| dp1 | 16384 | 1 | REUSE3 | 8 | 1 | 17264.6 | 1.0538 | 7344.5 | 8686.2 | 8546.3 | 7344.6 | 8686.3 | 8546.4 | 7.5842 | 1.0538 |  | 0.2 |

## Per-Request Results

These rows retain the stable request identity and correctness fields from each formal AISBench details artifact.
Complete prompt and prediction payloads remain in the immutable raw evidence.

| Point | Repetition | Request | Data ID | UUID | Success | Input Tokens | Output Tokens |
| --- | ---: | ---: | ---: | --- | --- | ---: | ---: |
| dp1-16384-bulk-o1-c8 | 1 | 1 | 1 | bb177b511ec247a488708bfa110893a9 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 2 | 0 | 382c65732fa84f1fb26382ca0361aea6 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 3 | 2 | 45219602f07148f9b2ed54779ba62b82 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 4 | 3 | 1f1213286de04091a4da098542ce30bc | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 5 | 4 | 54789c3088a8433aa645bfc3ed64f8ca | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 6 | 5 | d551226881b54ccfb8e4d849d43c66fa | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 7 | 6 | 5c988e7a7b46423cba0201fe9a6837c7 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 8 | 7 | 3257e5c8a9f342e29f8fa1ac1bdfde87 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 9 | 8 | 4787c50a57554cf190317c34f2fddd61 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 10 | 9 | 1462264f77554dc99c56212aeae8fb59 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 11 | 10 | a5dec5397ac24ee58349db11829b7584 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 12 | 11 | 9bbc70b6c95f48799da0b925bfccf8e7 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 13 | 12 | 0fd52c3ad7c741fe8102a44750b0c4de | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 14 | 13 | db31ff92670d499e86f74d411e7536ad | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 15 | 14 | f63f6d96ce444e64ab1927dae83cf41d | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 16 | 15 | 76e5446f43c141019429868524314eeb | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 17 | 16 | efc54970778f416aa38f8442780895da | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 18 | 17 | 7124f0a52b0b4ff6a440003e12d73f06 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 19 | 18 | b88ca9f41e294e2fb9065984a9daef61 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 20 | 19 | bad9c4f5d7874be295569f256d9f116d | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 21 | 20 | 1a415823887240e9990249672ca5dc7d | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 22 | 21 | 175e001fb60440d4b05bd2b1161649bd | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 23 | 22 | bc12a6237e6249bb85ec4804de137a9a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 24 | 23 | 5b85ac21325f4d78b6a842eecb0002f7 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 25 | 24 | 680f99fb094742d5b5d6b2c598e51a68 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 26 | 25 | b0058f84e40a44828ea763f7b95a23d5 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 27 | 26 | 6dce67a306e84f1cba7096015e98926a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 28 | 27 | 58eb682c276f4f12a20e40974b76b027 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 29 | 28 | c095e42bddbf4ec6a8ecb0c8fd43d52f | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 30 | 29 | e8bb40f74f2a47d8b3e2b833f867c99d | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 31 | 30 | 2e564df1747e4fc283b5723409076ba9 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 32 | 31 | 6d38edf91ba0435698d56d8ea930648f | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 33 | 32 | a17d9aef324f45f1b76dfea1f36abb28 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 34 | 33 | ec63db1be14346deb77a3c198819574e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 35 | 34 | b40636a7be394f408f8a2de419689e8c | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 36 | 35 | 1358b4f6e220419d8501a676cd309ce4 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 37 | 36 | 1d4acca187834f389cc6ce514abeda6b | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 38 | 37 | 05f2beb141d04cfeb24130e1f8479f0a | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 39 | 38 | c5f4f6e8a455405480fb225e2822796f | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 40 | 39 | 8ca45d164552407d9151f00ea84dd9ba | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 41 | 40 | 73532778b8cc4b5f910fa208884b7b30 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 42 | 41 | e6ae3a1aa5cb4652b47249b21eb7035f | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 43 | 42 | d5a995c58feb482f9fca090619245a67 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 44 | 43 | fd68b998eb9e4784ade9481d24c4b003 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 45 | 44 | 60f2b987e5ff471dbf43aafdc1b60a5e | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 46 | 45 | 131e08b3787e4e57b115d11b68915349 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 47 | 46 | b75182c908284f0493108a725a0fde31 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 48 | 47 | 45af3e8e4ef54888a9566be9d300a1a6 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 49 | 48 | cabf2c3250c14f1884e667d73474a057 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 50 | 49 | 798dc8108ee84549ade65b60c81e82b5 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 51 | 50 | 8a32b5c4f1674669ae6f35a27732d059 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 52 | 51 | f56d8fd8fd9046df8edafdc9ce1a05bc | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 53 | 52 | 8210d705a1c04a0da736a2c965029e51 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 54 | 53 | 63e16bcab67d41a5b473950d9504bebf | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 55 | 54 | 1494dbf4c8e04921bdeac768250ae4e1 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 56 | 55 | 643a9a40d08f4e08a31c138fcdff0fae | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 57 | 56 | 37c0bbe1c4d34805bb55254c601137c2 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 58 | 57 | e5ebd7e493c540f081c280de6c0dfc16 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 59 | 58 | 157a1f829c94491aacacc7784d6d1524 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 60 | 59 | df2e61997aee47b99f636fde629e16a3 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 61 | 60 | e73593d631c14292bada5c48f8b2933d | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 62 | 61 | 2156a752795540e5acf222759b382d65 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 63 | 62 | 577ec8a73d6846d09158e66e6f956440 | true | 16384 | 1 |
| dp1-16384-bulk-o1-c8 | 1 | 64 | 63 | 5581899ab281409a938835af58284d69 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 1 | 0 | 35b6d31781fa48c980c3a06ca745da20 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 2 | 1 | 148a1f5ab977482b877fe45869729005 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 3 | 2 | f07d6b7e9cc04bcf9c32792447c1832c | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 4 | 3 | 6290beb45ab34f449bbef4d94a80ad83 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 5 | 4 | c524f29a7d914b8b8e74ad56838ebf4c | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 6 | 5 | 423bccb7a5784a4dbd3ac0803d19be5a | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 7 | 6 | b1c93793ca5f45d791cc010457e37d49 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 8 | 7 | 493b981cee214a67854ed6b815854f16 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 9 | 8 | 35f563d18ff64256951d41af37e6a9d5 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 10 | 9 | ebb8c2bb2f1146c29ea478fa4c618144 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 11 | 10 | c85428405d3d442687232984564c9048 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 12 | 11 | 347513ac64814480a4151348e598a209 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 13 | 12 | 58dc99fd8ca44d5ba647384724b91ffe | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 14 | 13 | d3da59aed84f40a786941a71d1e79e07 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 15 | 14 | 387245c2430e4363bccd03b7966993d2 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 16 | 15 | d59191bf2ef34e8cbf1fb0cc9b474b93 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 17 | 16 | c1dfe77a2714497aab2e963de57dc9d9 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 18 | 17 | 12206777f0594441a316b6522184b8cc | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 19 | 18 | 7935a6f9b092406ab0f982908ca5cda5 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 20 | 19 | ce7223f0bc524a7d852192b36ac8aa6e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 21 | 20 | ae148762b5c34b9281a2050106970e2e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 22 | 21 | 86b1f7de24644d5fb899c3294dacfeb4 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 23 | 22 | 26a8459fa0214030b2f22b73dbf0afbb | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 24 | 23 | a92b344c68e74d2999a24ff10d1a91a0 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 25 | 24 | 8299934222c24976b19c7c6543388cc3 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 26 | 25 | 260c9dc3f3934dfd886bfe01606a3793 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 27 | 26 | d48161945e544bb3916a7ac0fac48c98 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 28 | 27 | 8832ea6ec95b4007901938735bb6e168 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 29 | 28 | 6304cb214acd438cb61f8f40a4aa0691 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 30 | 29 | 20bf20b6eb914eb48e0cd55e78eb1bf7 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 31 | 30 | 3196b7bde02e46d3b2124e3ac9a44de9 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 32 | 31 | b91da5c7137f4fb3b00b615c924c9bd0 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 33 | 32 | 2f812db57a9e4223a5f141936d84a385 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 34 | 33 | 7d6ccd0458cf44dbb281c9e84702b812 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 35 | 34 | 2e6fd13139bc4c3a87b799b80a393337 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 36 | 35 | 1e5e5f833f084c689819f3d004c468e3 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 37 | 36 | 8bccf497b89547969208e923a34c969e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 38 | 37 | 94ae3322b3d446ec927c7033b79e0844 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 39 | 38 | 96590884828d4427a4e0bec10bbfec90 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 40 | 39 | 439a202f756d4158bc510a3a1d900376 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 41 | 40 | b6db49d8a31a48ffa7d821e9a2b16f63 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 42 | 41 | 057b2e15e36740408e83dba8a846b396 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 43 | 42 | 25dfe0cabeb84f239af281f94fcb1bfc | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 44 | 43 | 2e8ae3c84f2e49c8998c262d0ee755da | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 45 | 44 | e8d03eca86124048997f4ba9f17f43e8 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 46 | 45 | ee5b7fafe64c4937905898fbf2ddcacb | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 47 | 46 | 60208bf8159d40e0afc4e6469e7d6e9f | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 48 | 47 | 8ebd8abd7d1149ba8193fed3b247e8b5 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 49 | 48 | a914d581015d4d519da721339a1eec46 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 50 | 49 | afaa280f170c46a5b2290ace64fbd6df | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 51 | 50 | f959be6300a044ebb5acdeca965bd362 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 52 | 51 | d28bc5cec80c44378f44107b64536e33 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 53 | 52 | 5ed5de0a579c4028a8d47ce75c8166dd | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 54 | 53 | 03d255ca2fbd41d0b667a1cf1b3e9f07 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 55 | 54 | 47cdd9b589b94c50bf617d70738b393e | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 56 | 55 | 79bfb07319a04bc999cc720bd1334334 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 57 | 56 | 98c35b93998b49078cfd18917f49912c | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 58 | 57 | 3687682fe04847d58e635bc514ff6d16 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 59 | 58 | 6614b73ef42746fe822d80dfc52c91ab | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 60 | 59 | f0fe6e1480564daeba0377acf3e3fe21 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 61 | 60 | 443394f32e62444ab2b9a22d3f7d48a9 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 62 | 61 | 92965d449ea74ecdb5850f619d82573f | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 63 | 62 | 3670745421774486a283f81582cf6b67 | true | 16384 | 1 |
| dp1-16384-layerwise-o1-c8 | 1 | 64 | 63 | 51502dd22f844883a1b5942cafb9ec05 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 1 | 0 | 49c5b4add5714dc4bd837f963d41f311 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 2 | 1 | 500d862b40994767a4ba747f85a9f0bc | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 3 | 2 | 1a4a8569170540d9adb606a4307234a1 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 4 | 3 | f03a5eac91d9405695dbab39ce2c500f | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 5 | 4 | d66afe959c9f44dbb3d33ac3a1f08942 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 6 | 5 | 3e24b2a93c7b40e280cd91ef0574ef7a | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 7 | 6 | a9a2419066f44c15bff58e80298b4076 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 8 | 7 | 79ab370d65aa43848b1eeaa39764e152 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 9 | 8 | bb3e4ec2563e46a39ffb24eea3feabfb | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 10 | 9 | ad1b5ab0bc294f3ba96f5845ac2a7211 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 11 | 10 | 8105bbc766ae45cea4a50d32257a4369 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 12 | 11 | a953b259d7114890a2affa13398b5d31 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 13 | 12 | 31fcf0e44e5f4fcdbedab867705688f4 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 14 | 13 | 04047c009867407aa91b94f26f1d33be | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 15 | 14 | 94ff788bc4af49a883805daa6ce3b829 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 16 | 15 | 800a9b6bdf5343018705bcda7d66ba51 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 17 | 16 | 340a97c230f7417eafcae5131e0a4668 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 18 | 17 | ea33ff133abc44b694640def6896205b | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 19 | 18 | 9b867504db064519bd6b85787c79bd94 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 20 | 19 | a9ee0d40fb22451c86776c1f572bba5e | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 21 | 20 | aba0687d990142169a3c019f259ff4eb | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 22 | 21 | 6c9328c2da58415ab8ff4b026c6fb6c2 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 23 | 22 | ac36a6f400764cdd9eca23a4642241ec | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 24 | 23 | 4f25c8c8d3584b34832349a68d9c1ba5 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 25 | 24 | 31997fd81ada406aa2d39bb2f8a472bf | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 26 | 25 | 71e6603872c9455780a13632bade3b2c | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 27 | 26 | 2d23d3bef354483dbf173da057afb8e7 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 28 | 27 | 82e07b32272a4bb7aa30177253071cfb | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 29 | 28 | 392a64c2f3e844d7a73868eef17c9724 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 30 | 29 | 79576e128c26453ab5b50b9044a9b29d | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 31 | 30 | 79deaec3e9a541248a16febeea22a201 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 32 | 31 | 2e60df6dcdec4b10a72fe29402524dda | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 33 | 32 | 1c945dc4a3774485a4b3efd1afd3ff2b | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 34 | 33 | 0d3b5165f0764109935273d6c6b00604 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 35 | 34 | e08c1a4a9745435b814c4432bb59e797 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 36 | 35 | da069fc97a22467fa7c93336229d0914 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 37 | 36 | f2004d3c635840d6b8083c607e738137 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 38 | 37 | 81c881d5dc5140899f4dd9e659df96dd | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 39 | 38 | cf3b1d1c526e45f99f40515a6102158e | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 40 | 39 | 5fd60fa1fb0d4fe8a5f46aa76d1c80ad | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 41 | 40 | 4f9e65e27e3e4b949295be850f625be7 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 42 | 41 | 58ef9e92956b4a868eb1854998bd7f8b | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 43 | 42 | 1df23d9199f746cc98ab7b3eb074e319 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 44 | 43 | a3c923fc58ac44e391fc602ab960a395 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 45 | 44 | ceda601ab2834eb1ae0f4347f682e96f | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 46 | 45 | 58acccda8eeb4e2ea63fb3d886622904 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 47 | 46 | 74f7e4d1eba1400785c54ba49dc2f4bd | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 48 | 47 | 8d5a18a9b7cf4d0c928b01c140812c41 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 49 | 48 | a2d5e356f3a14b029cf8464236e433c8 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 50 | 49 | e1d493e8999345b2a5ecbcdcc5ddbac7 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 51 | 50 | 9d6bc23a2ddf4d88b88f9b676d3dac3d | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 52 | 51 | 3bd157b5cda343f08dccf9c4d129e1f3 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 53 | 52 | 542231a1d39e461da6d7203c5be376d3 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 54 | 53 | f0cf758e39c64c05adb277a14194b8a8 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 55 | 54 | 594b0f87d0ba4cd790b809ce646e7e46 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 56 | 55 | 566aff1da3f4434cbd021c74fdcfdb22 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 57 | 56 | 20aeb5a08a094d9c8c31067e6756000f | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 58 | 57 | 80b96ca0e213487fbd089dd1570961f2 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 59 | 58 | 187193d780734e57a49f804edf9888e2 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 60 | 59 | d3f1f40acf104ddcad222e91b72f3952 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 61 | 60 | b5611b615fa34079b4e531a6db36a24f | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 62 | 61 | aff6db17e4df4b5a8a5cfc6d54dc8579 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 63 | 62 | 05b495758ac6471d9d92d6e803642416 | true | 16384 | 1 |
| dp1-16384-reuse3-o1-c8 | 1 | 64 | 63 | 44f729f5c3574662a54d77968e6b3cdf | true | 16384 | 1 |

## Direct Ratios

| Comparison | Topology | Input | Output | Concurrency | Repetition | Metric | Ratio |
| --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.759051 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.759046 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.33225 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.28444 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.30135 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.33227 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.28441 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.30136 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 1.00252 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.759046 |
| LAYERWISE / BULK | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 1 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.897059 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.89708 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.09332 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.20926 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.22526 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.09332 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.20925 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.22524 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 1.00202 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.89708 |
| REUSE3 / LAYERWISE | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 1 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Input Token Throughput | 0.680913 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Request Throughput | 0.680925 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Median | 1.45658 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT Max | 1.55322 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | TTFT P95 | 1.59449 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Median | 1.4566 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL Max | 1.55318 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | E2EL P95 | 1.59448 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Achieved Concurrency | 1.00454 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | Output Token Throughput | 0.680925 |
| REUSE3 / BULK | dp1 | 16384 | 1 | 8 | 1 | ITL P95 | 1 |
