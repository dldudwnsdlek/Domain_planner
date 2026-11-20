// 자동 생성: scripts/make_demo_data.py — 저장된 실제 API 샘플 + 실제 판정 엔진, 요청 분석만 고정값
window.DEMO_DATA = {
 "chat": {
  "session_id": "s-demo",
  "run_id": "r-ee490a6b29",
  "status": "ok",
  "reply": "조건(2026-11-21 · 18:00 이후 시작 · 대학로 · 연극 · 23:30까지 망원역 도착 · 50,000원 이하)에 맞는 공연 5편을 찾았어요.",
  "understood": {
   "date": "2026-11-21",
   "start_after": "18:00",
   "region": "대학로",
   "genre": "연극",
   "home_by": "23:30",
   "home_location": "망원역",
   "budget_max": 50000
  },
  "defaults_applied": [],
  "recommendations": [
   {
    "performance_id": "PF306792",
    "title": "아일랜드",
    "genre": "연극",
    "poster_url": "http://www.kopis.or.kr/upload/pfmPoster/PF_PF306792_261118_123938.gif",
    "venue": {
     "name": "소극장 플랫폼74",
     "address": "서울특별시 종로구 동숭길 74 (동숭동)",
     "map_url": "https://map.kakao.com/link/map/%EC%86%8C%EA%B7%B9%EC%9E%A5%20%ED%94%8C%EB%9E%AB%ED%8F%BC74,37.5815333,127.0043015"
    },
    "date": "2026-11-21",
    "showtimes": [
     {
      "start": "18:00",
      "end": "19:15",
      "home_arrival": "20:00",
      "verdict": "PASS"
     }
    ],
    "min_price": 30000,
    "price_raw": "전석 30,000원",
    "age_rating": "15세 이상",
    "ticket_links": [
     {
      "name": "놀유니버스",
      "url": "http://ticket.interpark.com/Ticket/Goods/GoodsInfo.asp?GoodsCode=26016636"
     }
    ],
    "transit": {
     "total_min": 35,
     "summary": "4호선 → 5호선 → 6호선",
     "map_url": "https://map.kakao.com/link/by/traffic/%EC%B6%9C%EB%B0%9C,37.582299,127.001699/%EB%8F%84%EC%B0%A9,37.555996,126.910182"
    },
    "weather": {
     "status": "ok",
     "summary": "18시 강수확률 0% · 기온 -2℃",
     "hours": [
      {
       "time": "18:00",
       "forecast_time": "18:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -2
      },
      {
       "time": "19:15",
       "forecast_time": "19:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      },
      {
       "time": "20:00",
       "forecast_time": "20:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      }
     ]
    },
    "evidence": [
     "KOPIS 러닝타임 75분",
     "토 18:00 회차",
     "최저가 30,000원",
     "카카오 대중교통 35분",
     "기상청 단기예보"
    ]
   },
   {
    "performance_id": "PF305818",
    "title": "증언의 목소리들",
    "genre": "연극",
    "poster_url": "http://www.kopis.or.kr/upload/pfmPoster/PF_PF305818_261109_150230.gif",
    "venue": {
     "name": "창작공간 BBB",
     "address": "서울특별시 종로구 이화장길 46 (이화동)",
     "map_url": "https://map.kakao.com/link/map/%EC%B0%BD%EC%9E%91%EA%B3%B5%EA%B0%84%20BBB,37.577362,127.004709"
    },
    "date": "2026-11-21",
    "showtimes": [
     {
      "start": "19:00",
      "end": "20:40",
      "home_arrival": "21:25",
      "verdict": "PASS"
     }
    ],
    "min_price": 15000,
    "price_raw": "전석 15,000원",
    "age_rating": "만 6세 이상",
    "ticket_links": [
     {
      "name": "놀유니버스",
      "url": "http://ticket.interpark.com/Ticket/Goods/GoodsInfo.asp?GoodsCode=26016033"
     }
    ],
    "transit": {
     "total_min": 35,
     "summary": "4호선 → 5호선 → 6호선",
     "map_url": "https://map.kakao.com/link/by/traffic/%EC%B6%9C%EB%B0%9C,37.582299,127.001699/%EB%8F%84%EC%B0%A9,37.555996,126.910182"
    },
    "weather": {
     "status": "ok",
     "summary": "19시 강수확률 0% · 기온 -3℃",
     "hours": [
      {
       "time": "19:00",
       "forecast_time": "19:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      },
      {
       "time": "20:40",
       "forecast_time": "21:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      },
      {
       "time": "21:25",
       "forecast_time": "21:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      }
     ]
    },
    "evidence": [
     "KOPIS 러닝타임 100분",
     "토 19:00 회차",
     "최저가 15,000원",
     "카카오 대중교통 35분",
     "기상청 단기예보"
    ]
   },
   {
    "performance_id": "PF305998",
    "title": "한국마임: 언제 어디서나 마임",
    "genre": "연극",
    "poster_url": "http://www.kopis.or.kr/upload/pfmPoster/PF_PF305998_261110_145605.gif",
    "venue": {
     "name": "봄날아트홀 (구. 아리랑소극장)",
     "address": "서울특별시 종로구 동숭길 39 (동숭동)",
     "map_url": "https://map.kakao.com/link/map/%EB%B4%84%EB%82%A0%EC%95%84%ED%8A%B8%ED%99%80%20%28%EA%B5%AC.%20%EC%95%84%EB%A6%AC%EB%9E%91%EC%86%8C%EA%B7%B9%EC%9E%A5%29,37.5799517,127.00425100000007"
    },
    "date": "2026-11-21",
    "showtimes": [
     {
      "start": "19:00",
      "end": "20:10",
      "home_arrival": "20:55",
      "verdict": "PASS"
     }
    ],
    "min_price": 20000,
    "price_raw": "전석 20,000원",
    "age_rating": "전체 관람가",
    "ticket_links": [
     {
      "name": "놀유니버스",
      "url": "http://ticket.interpark.com/Ticket/Goods/GoodsInfo.asp?GoodsCode=26015971"
     }
    ],
    "transit": {
     "total_min": 35,
     "summary": "4호선 → 5호선 → 6호선",
     "map_url": "https://map.kakao.com/link/by/traffic/%EC%B6%9C%EB%B0%9C,37.582299,127.001699/%EB%8F%84%EC%B0%A9,37.555996,126.910182"
    },
    "weather": {
     "status": "ok",
     "summary": "19시 강수확률 0% · 기온 -3℃",
     "hours": [
      {
       "time": "19:00",
       "forecast_time": "19:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      },
      {
       "time": "20:10",
       "forecast_time": "20:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      },
      {
       "time": "20:55",
       "forecast_time": "21:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      }
     ]
    },
    "evidence": [
     "KOPIS 러닝타임 70분",
     "토 19:00 회차",
     "최저가 20,000원",
     "카카오 대중교통 35분",
     "기상청 단기예보"
    ]
   },
   {
    "performance_id": "PF306527",
    "title": "없는 대화",
    "genre": "연극",
    "poster_url": "http://www.kopis.or.kr/upload/pfmPoster/PF_PF306527_261116_143307.gif",
    "venue": {
     "name": "제이원 씨어터 (구. 서완소극장, 구. 씨어터고리)",
     "address": "서울특별시 종로구 창경궁로34길 18-12",
     "map_url": "https://map.kakao.com/link/map/%EC%A0%9C%EC%9D%B4%EC%9B%90%20%EC%94%A8%EC%96%B4%ED%84%B0%20%28%EA%B5%AC.%20%EC%84%9C%EC%99%84%EC%86%8C%EA%B7%B9%EC%9E%A5%2C%20%EA%B5%AC.%20%EC%94%A8%EC%96%B4%ED%84%B0%EA%B3%A0%EB%A6%AC%29,37.5841705,127.00042899999994"
    },
    "date": "2026-11-21",
    "showtimes": [
     {
      "start": "19:00",
      "end": "20:40",
      "home_arrival": "21:25",
      "verdict": "PASS"
     }
    ],
    "min_price": 40000,
    "price_raw": "전석 40,000원",
    "age_rating": "만 12세 이상",
    "ticket_links": [
     {
      "name": "놀유니버스",
      "url": "http://ticket.interpark.com/Ticket/Goods/GoodsInfo.asp?GoodsCode=26016438"
     }
    ],
    "transit": {
     "total_min": 35,
     "summary": "4호선 → 5호선 → 6호선",
     "map_url": "https://map.kakao.com/link/by/traffic/%EC%B6%9C%EB%B0%9C,37.582299,127.001699/%EB%8F%84%EC%B0%A9,37.555996,126.910182"
    },
    "weather": {
     "status": "ok",
     "summary": "19시 강수확률 0% · 기온 -3℃",
     "hours": [
      {
       "time": "19:00",
       "forecast_time": "19:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      },
      {
       "time": "20:40",
       "forecast_time": "21:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      },
      {
       "time": "21:25",
       "forecast_time": "21:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      }
     ]
    },
    "evidence": [
     "KOPIS 러닝타임 100분",
     "토 19:00 회차",
     "최저가 40,000원",
     "카카오 대중교통 35분",
     "기상청 단기예보"
    ]
   },
   {
    "performance_id": "PF305857",
    "title": "오나리스 [서울]",
    "genre": "연극",
    "poster_url": "http://www.kopis.or.kr/upload/pfmPoster/PF_PF305857_261109_161727.png",
    "venue": {
     "name": "북극곰소극장",
     "address": "서울특별시 종로구 이화장1길 24 (이화동)",
     "map_url": "https://map.kakao.com/link/map/%EB%B6%81%EA%B7%B9%EA%B3%B0%EC%86%8C%EA%B7%B9%EC%9E%A5,37.5773694,127.00575709999998"
    },
    "date": "2026-11-21",
    "showtimes": [
     {
      "start": "19:30",
      "end": "20:45",
      "home_arrival": "21:30",
      "verdict": "PASS"
     }
    ],
    "min_price": 15000,
    "price_raw": "전석 15,000원",
    "age_rating": "만 16세 이상",
    "ticket_links": [
     {
      "name": "플레이티켓",
      "url": "http://playticket.co.kr/nav/detail.html?idx=4772"
     }
    ],
    "transit": {
     "total_min": 35,
     "summary": "4호선 → 5호선 → 6호선",
     "map_url": "https://map.kakao.com/link/by/traffic/%EC%B6%9C%EB%B0%9C,37.582299,127.001699/%EB%8F%84%EC%B0%A9,37.555996,126.910182"
    },
    "weather": {
     "status": "ok",
     "summary": "19시 강수확률 0% · 기온 -3℃",
     "hours": [
      {
       "time": "19:30",
       "forecast_time": "19:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      },
      {
       "time": "20:45",
       "forecast_time": "21:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      },
      {
       "time": "21:30",
       "forecast_time": "21:00",
       "pop": 0,
       "pty": "없음",
       "sky": "맑음",
       "tmp": -3
      }
     ]
    },
    "evidence": [
     "KOPIS 러닝타임 75분",
     "토 19:30 회차",
     "최저가 15,000원",
     "카카오 대중교통 35분",
     "기상청 단기예보"
    ]
   }
  ],
  "excluded": [
   {
    "performance_id": "PF306557",
    "title": "제3회 연문페스티벌, 복덕방",
    "reason_code": "START_TOO_EARLY",
    "reason": "18:00 이후에 시작하는 회차가 없어요"
   },
   {
    "performance_id": "PF306452",
    "title": "모든 날, 모든 순간 [대학로]",
    "reason_code": "START_TOO_EARLY",
    "reason": "18:00 이후에 시작하는 회차가 없어요"
   },
   {
    "performance_id": "PF305847",
    "title": "엄마와 아들: 아들, 엄마도 처음이야! [대학로]",
    "reason_code": "START_TOO_EARLY",
    "reason": "18:00 이후에 시작하는 회차가 없어요"
   },
   {
    "performance_id": "PF305551",
    "title": "모든 날 모든 순간",
    "reason_code": "START_TOO_EARLY",
    "reason": "18:00 이후에 시작하는 회차가 없어요"
   },
   {
    "performance_id": "PF305411",
    "title": "운명",
    "reason_code": "NOT_DAEHAKRO",
    "reason": "대학로 공연이 아니에요"
   }
  ],
  "suggestions": [],
  "facts": null,
  "assumptions": [
   "퇴장 여유 10분 포함",
   "대중교통 시간은 시간대·막차 미반영",
   "가격·회차는 변동될 수 있으니 예매처에서 최종 확인하세요"
  ],
  "sources": [
   "출처: (재)예술경영지원센터 공연예술통합전산망(www.kopis.or.kr)",
   "카카오맵",
   "기상청 단기예보(공공누리 제1유형)"
  ],
  "trace": [
   {
    "seq": 4,
    "label": "요청 분석 — plan_request",
    "elapsed_ms": 0,
    "is_replan": false,
    "ok": true
   },
   {
    "seq": 29,
    "label": "계획 수립 — 규칙 템플릿 · 동시에 후보 선반입: 공연 목록 조회 ×1 · 공연 상세 ×10",
    "elapsed_ms": 3,
    "is_replan": false,
    "ok": true
   },
   {
    "seq": 53,
    "label": "Tool 실행 — 공연장 좌표 ×5 · 장소 검색 ×1 · 이동시간 ×5 (후보는 계획 중 선반입)",
    "elapsed_ms": 25,
    "is_replan": false,
    "ok": true
   },
   {
    "seq": 56,
    "label": "판정 — 통과 5 / 탈락 4 / 불가 0",
    "elapsed_ms": 0,
    "is_replan": false,
    "ok": true
   },
   {
    "seq": 68,
    "label": "날씨·지도 추가 — 상위 5편 · 날씨 조회 ×5",
    "elapsed_ms": 1,
    "is_replan": false,
    "ok": true
   },
   {
    "seq": 70,
    "label": "응답 생성 — 템플릿",
    "elapsed_ms": 0,
    "is_replan": false,
    "ok": true
   }
  ],
  "replan_count": 0,
  "warnings": [],
  "elapsed_ms": 34,
  "request": "11월 21일 토요일 저녁 6시 이후 대학로에서 연극 보고, 밤 11시 반까지 망원역 도착해야 해. 5만원 이하로."
 },
 "plans": [
  {
   "id": 2,
   "performance_id": "MANUAL",
   "title": "저녁 식사 (직접 입력)",
   "venue_name": "혜화역 근처",
   "venue_address": null,
   "date": "2026-11-21",
   "start_time": "17:00",
   "end_time": "18:30",
   "price": null,
   "ticket_url": null,
   "memo": "공연 전 식사",
   "session_id": null,
   "created_at": "2026-11-20T10:07:04+09:00",
   "updated_at": "2026-11-20T10:07:04+09:00",
   "overlaps": [
    1
   ]
  },
  {
   "id": 1,
   "performance_id": "PF306792",
   "title": "아일랜드",
   "venue_name": "소극장 플랫폼74",
   "venue_address": "서울특별시 종로구 동숭길 74 (동숭동)",
   "date": "2026-11-21",
   "start_time": "18:00",
   "end_time": "19:15",
   "price": 30000,
   "ticket_url": "http://ticket.interpark.com/Ticket/Goods/GoodsInfo.asp?GoodsCode=26016636",
   "memo": null,
   "session_id": "s-demo",
   "created_at": "2026-11-20T10:07:04+09:00",
   "updated_at": "2026-11-20T10:07:04+09:00",
   "overlaps": [
    2
   ]
  }
 ],
 "logs": {
  "sessions": [
   {
    "session_id": "s-demo",
    "runs": 2,
    "events": 78,
    "first_ts": "2026-11-20T10:07:04.492+09:00",
    "last_ts": "2026-11-20T10:07:04.528+09:00"
   }
  ],
  "events": [
   {
    "event_id": "68649928-51fc-45da-9b9d-0d60dea44058",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 1,
    "ts": "2026-11-20T10:07:04.492+09:00",
    "type": "run.started",
    "node": null,
    "payload": {
     "message": "11월 21일 토요일 저녁 6시 이후 대학로에서 연극 보고, 밤 11시 반까지 망원역 도착해야 해. 5만원 이하로."
    }
   },
   {
    "event_id": "47bae25a-0ecb-4fa7-a3d3-57bbe6289e04",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 2,
    "ts": "2026-11-20T10:07:04.494+09:00",
    "type": "node.entered",
    "node": "analyze",
    "payload": {}
   },
   {
    "event_id": "0cc1fc0d-d721-4264-b170-b35e7f1ee019",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 3,
    "ts": "2026-11-20T10:07:04.494+09:00",
    "type": "llm.decision",
    "node": "analyze",
    "payload": {
     "kind": "intent",
     "value": "plan_request",
     "reason": "날짜·지역·장르와 시간·귀가·예산 제약이 있는 추천 요청"
    }
   },
   {
    "event_id": "442c2dc1-7b88-48cd-9dad-3ed29ded0ae1",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 4,
    "ts": "2026-11-20T10:07:04.495+09:00",
    "type": "node.exited",
    "node": "analyze",
    "payload": {
     "elapsed_ms": 0,
     "summary": "plan_request",
     "ok": true
    }
   },
   {
    "event_id": "b58240c2-f9df-4ff1-8d1e-df82bfc4d7bd",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 5,
    "ts": "2026-11-20T10:07:04.495+09:00",
    "type": "node.entered",
    "node": "plan",
    "payload": {}
   },
   {
    "event_id": "e8e385dc-ed26-42b6-83c0-5a3e470f1d6a",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 6,
    "ts": "2026-11-20T10:07:04.495+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "search_performances",
     "args": {
      "date_from": "2026-11-21",
      "page": 1,
      "size": 20,
      "region": "대학로",
      "genre": "연극"
     }
    }
   },
   {
    "event_id": "36c8d482-9720-45d3-ad1e-8fda3b3764f7",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 7,
    "ts": "2026-11-20T10:07:04.495+09:00",
    "type": "plan.fallback",
    "node": "plan",
    "payload": {
     "reason": "LLM 계획기 없음",
     "llm_selected": [],
     "value": [
      "search_performances",
      "get_performance_detail",
      "search_places",
      "get_transit_time",
      "get_weather"
     ]
    }
   },
   {
    "event_id": "1187ee4c-0e9b-405d-bdfe-9398d52e75be",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 8,
    "ts": "2026-11-20T10:07:04.496+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "search_performances",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "date_from": "2026-11-21",
      "page": 1,
      "size": 20,
      "region": "대학로",
      "genre": "연극"
     },
     "count": 30
    }
   },
   {
    "event_id": "14993f71-77f4-456f-81a5-cd76773075be",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 9,
    "ts": "2026-11-20T10:07:04.496+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF306792",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "c616daa9-8a29-4f70-aebd-6ab367e17907",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 10,
    "ts": "2026-11-20T10:07:04.496+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF306557",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "2d3cd952-097d-4b92-a735-c631ee60ebb9",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 11,
    "ts": "2026-11-20T10:07:04.496+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF306527",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "82ffba27-d9ca-4045-aa02-4590cf51b1ed",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 12,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF306452",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "18d660ee-92b9-4759-a2b0-7272fb720bab",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 13,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF305998",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "d31cd633-57d7-4d09-97cb-8562ee98f4da",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 14,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF306792",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "3751aa68-fe0c-4fd3-8813-1bb4eb00da50",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 15,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF306557",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "5240d2ea-2d3d-4077-bec4-697d43bd654c",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 16,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF306527",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "7d29b399-3252-420a-a69d-8040d0368148",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 17,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF306452",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "58193f36-20ce-4a09-ab25-5fc4e73611fb",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 18,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF305998",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "c948d979-142f-4a9e-a34f-9b7a4169e847",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 19,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF305857",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "85559641-0506-431e-9d55-28845f1c4f3c",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 20,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF305847",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "317d1bee-c853-4aaa-ad23-699e79819669",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 21,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF305818",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "5bc86c10-b246-4e66-938a-543c07c30cca",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 22,
    "ts": "2026-11-20T10:07:04.497+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF305551",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "257d96c2-0189-4c4c-a220-beb8190eb2cb",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 23,
    "ts": "2026-11-20T10:07:04.498+09:00",
    "type": "tool.requested",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF305411",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "978ea365-d90c-446b-b4c3-40e84fdf3601",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 24,
    "ts": "2026-11-20T10:07:04.498+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF305857",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "81993050-3b1a-4617-a7d8-c92743249032",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 25,
    "ts": "2026-11-20T10:07:04.498+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF305847",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "7a7c1b49-e766-4ffd-abfb-4fda87e1ec87",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 26,
    "ts": "2026-11-20T10:07:04.498+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF305818",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "47665472-f82e-48ef-999b-94b09e9171a6",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 27,
    "ts": "2026-11-20T10:07:04.498+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF305551",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "8e534990-2e74-4426-9c14-988d26af02e3",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 28,
    "ts": "2026-11-20T10:07:04.498+09:00",
    "type": "tool.responded",
    "node": "plan",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF305411",
      "include_venue": false
     }
    }
   },
   {
    "event_id": "5deb3168-f46b-415a-8733-b8bb71476e7e",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 29,
    "ts": "2026-11-20T10:07:04.498+09:00",
    "type": "node.exited",
    "node": "plan",
    "payload": {
     "elapsed_ms": 3,
     "summary": "규칙 템플릿",
     "ok": true
    }
   },
   {
    "event_id": "4dfd226b-c9ae-4508-8b59-60a4ad32ffa8",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 30,
    "ts": "2026-11-20T10:07:04.499+09:00",
    "type": "node.entered",
    "node": "execute",
    "payload": {}
   },
   {
    "event_id": "1592476d-9f52-4c86-895d-9bb0f89e8191",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 31,
    "ts": "2026-11-20T10:07:04.499+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF306792",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "4a089010-fa66-40e3-bc47-f2ca2e1dbd71",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 32,
    "ts": "2026-11-20T10:07:04.499+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF306527",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "3a750ee3-c431-46bb-bf7e-5f071b158b80",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 33,
    "ts": "2026-11-20T10:07:04.499+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF305998",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "329b894f-e0b6-48fc-97fd-087abeff3432",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 34,
    "ts": "2026-11-20T10:07:04.499+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF305857",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "c697abd2-9342-46ee-b203-f30027281a1f",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 35,
    "ts": "2026-11-20T10:07:04.499+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "args": {
      "performance_id": "PF305818",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "40ff510b-b177-4223-b442-9252d36c36ba",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 36,
    "ts": "2026-11-20T10:07:04.499+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF306792",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "ae7527d0-1cbe-408b-8119-693e5f213c44",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 37,
    "ts": "2026-11-20T10:07:04.499+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF306527",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "8f45a50b-9807-4fdd-891c-b42c41cd0225",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 38,
    "ts": "2026-11-20T10:07:04.500+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF305998",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "68cd5bb6-c734-44ed-afa7-137f1611752c",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 39,
    "ts": "2026-11-20T10:07:04.500+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF305857",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "6e274cc8-efd8-4de1-a68e-965231fe7417",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 40,
    "ts": "2026-11-20T10:07:04.500+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_performance_detail",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "performance_id": "PF305818",
      "include_venue": true
     }
    }
   },
   {
    "event_id": "0a5bf16a-0312-4af9-b768-041c31b306b2",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 41,
    "ts": "2026-11-20T10:07:04.500+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "search_places",
     "args": {
      "mode": "geocode",
      "query": "망원역"
     }
    }
   },
   {
    "event_id": "474f47ee-c73d-4f9d-af0e-d4f10b939a97",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 42,
    "ts": "2026-11-20T10:07:04.500+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "search_places",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "mode": "geocode",
      "query": "망원역"
     },
     "count": 5
    }
   },
   {
    "event_id": "354b00cd-f823-4020-a5c2-79903d558861",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 43,
    "ts": "2026-11-20T10:07:04.500+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "args": {
      "from_lat": 37.5815333,
      "from_lng": 127.0043015,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "baa330f2-fe37-4d73-91ad-662f4c85db46",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 44,
    "ts": "2026-11-20T10:07:04.500+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "args": {
      "from_lat": 37.5841705,
      "from_lng": 127.00042899999994,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "7a0f7587-bf64-495f-86e2-38646f75d2c2",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 45,
    "ts": "2026-11-20T10:07:04.500+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "args": {
      "from_lat": 37.5799517,
      "from_lng": 127.00425100000007,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "788517d4-adc9-4e36-90ea-0b8c2d54d580",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 46,
    "ts": "2026-11-20T10:07:04.500+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "args": {
      "from_lat": 37.5773694,
      "from_lng": 127.00575709999998,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "fdd9dba2-4116-45fe-8d8e-b2e06cc1a4bb",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 47,
    "ts": "2026-11-20T10:07:04.519+09:00",
    "type": "tool.requested",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "args": {
      "from_lat": 37.577362,
      "from_lng": 127.004709,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "ddbff01e-3283-477d-a618-308e672c7448",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 48,
    "ts": "2026-11-20T10:07:04.519+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "ok": true,
     "code": null,
     "elapsed_ms": 18,
     "args": {
      "from_lat": 37.5815333,
      "from_lng": 127.0043015,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "152009a2-bfb2-49ff-b9b9-5ef4becfca35",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 49,
    "ts": "2026-11-20T10:07:04.520+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "ok": true,
     "code": null,
     "elapsed_ms": 19,
     "args": {
      "from_lat": 37.5841705,
      "from_lng": 127.00042899999994,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "a0574677-1dd7-4155-b105-06670cfb878f",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 50,
    "ts": "2026-11-20T10:07:04.522+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "ok": true,
     "code": null,
     "elapsed_ms": 1,
     "args": {
      "from_lat": 37.5773694,
      "from_lng": 127.00575709999998,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "11eb7f3d-2c5c-4eba-bfb1-96141616c48d",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 51,
    "ts": "2026-11-20T10:07:04.523+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "ok": true,
     "code": null,
     "elapsed_ms": 2,
     "args": {
      "from_lat": 37.5799517,
      "from_lng": 127.00425100000007,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "8e2e9c87-cc8b-4a2f-87dd-f30c7594134b",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 52,
    "ts": "2026-11-20T10:07:04.524+09:00",
    "type": "tool.responded",
    "node": "execute",
    "payload": {
     "tool": "get_transit_time",
     "ok": true,
     "code": null,
     "elapsed_ms": 3,
     "args": {
      "from_lat": 37.577362,
      "from_lng": 127.004709,
      "to_lat": 37.5560826563712,
      "to_lng": 126.910094329982
     }
    }
   },
   {
    "event_id": "4de5f9fd-4961-41ca-9001-029028baebde",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 53,
    "ts": "2026-11-20T10:07:04.524+09:00",
    "type": "node.exited",
    "node": "execute",
    "payload": {
     "elapsed_ms": 25,
     "summary": "상세 9건 (계획 중 선반입)",
     "ok": true
    }
   },
   {
    "event_id": "59050982-c782-4a4a-ba40-17730b184955",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 54,
    "ts": "2026-11-20T10:07:04.524+09:00",
    "type": "node.entered",
    "node": "judge",
    "payload": {}
   },
   {
    "event_id": "e17af1a6-5456-43c2-8876-38e9aa622db0",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 55,
    "ts": "2026-11-20T10:07:04.525+09:00",
    "type": "constraint.evaluated",
    "node": "judge",
    "payload": {
     "pass": 5,
     "fail": 4,
     "unknown": 0,
     "top_reasons": {
      "START_TOO_EARLY": 4
     }
    }
   },
   {
    "event_id": "0be6395c-2097-43b1-8b62-619cb30e5317",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 56,
    "ts": "2026-11-20T10:07:04.525+09:00",
    "type": "node.exited",
    "node": "judge",
    "payload": {
     "elapsed_ms": 0,
     "summary": "통과 5 / 탈락 4 / 불가 0",
     "ok": true
    }
   },
   {
    "event_id": "dd25fbcc-5645-44c1-9666-1dd74bbd9415",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 57,
    "ts": "2026-11-20T10:07:04.525+09:00",
    "type": "node.entered",
    "node": "enrich",
    "payload": {}
   },
   {
    "event_id": "25065769-5ebe-4b0d-8f5b-6856bf3e9a71",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 58,
    "ts": "2026-11-20T10:07:04.525+09:00",
    "type": "tool.requested",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "args": {
      "lat": 37.5815333,
      "lng": 127.0043015,
      "date": "2026-11-21",
      "hours": [
       "18:00",
       "19:15",
       "20:00"
      ]
     }
    }
   },
   {
    "event_id": "8fff084f-ed95-4d4f-960e-d95e6f1ab7a0",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 59,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "tool.responded",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "lat": 37.5815333,
      "lng": 127.0043015,
      "date": "2026-11-21",
      "hours": [
       "18:00",
       "19:15",
       "20:00"
      ]
     }
    }
   },
   {
    "event_id": "4344ce7b-5d7d-4649-9a3c-9e2261f8e407",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 60,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "tool.requested",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "args": {
      "lat": 37.577362,
      "lng": 127.004709,
      "date": "2026-11-21",
      "hours": [
       "19:00",
       "20:40",
       "21:25"
      ]
     }
    }
   },
   {
    "event_id": "4a55f8ad-41a8-49f4-91ba-1f937fefc01d",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 61,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "tool.responded",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "lat": 37.577362,
      "lng": 127.004709,
      "date": "2026-11-21",
      "hours": [
       "19:00",
       "20:40",
       "21:25"
      ]
     }
    }
   },
   {
    "event_id": "c3f74f03-d6f2-488b-8c60-2c5129ebda75",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 62,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "tool.requested",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "args": {
      "lat": 37.5799517,
      "lng": 127.00425100000007,
      "date": "2026-11-21",
      "hours": [
       "19:00",
       "20:10",
       "20:55"
      ]
     }
    }
   },
   {
    "event_id": "b0f1af1b-f50b-41ad-8f55-512c08c3eaa5",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 63,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "tool.responded",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "lat": 37.5799517,
      "lng": 127.00425100000007,
      "date": "2026-11-21",
      "hours": [
       "19:00",
       "20:10",
       "20:55"
      ]
     }
    }
   },
   {
    "event_id": "8b5af9f4-beec-40c3-afdd-28a976b0e7d0",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 64,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "tool.requested",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "args": {
      "lat": 37.5841705,
      "lng": 127.00042899999994,
      "date": "2026-11-21",
      "hours": [
       "19:00",
       "20:40",
       "21:25"
      ]
     }
    }
   },
   {
    "event_id": "cf04f7a5-fb18-4056-b881-f57f2eaef551",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 65,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "tool.responded",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "lat": 37.5841705,
      "lng": 127.00042899999994,
      "date": "2026-11-21",
      "hours": [
       "19:00",
       "20:40",
       "21:25"
      ]
     }
    }
   },
   {
    "event_id": "467da0e3-8c63-488f-8fce-a7960dc9c8ac",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 66,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "tool.requested",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "args": {
      "lat": 37.5773694,
      "lng": 127.00575709999998,
      "date": "2026-11-21",
      "hours": [
       "19:30",
       "20:45",
       "21:30"
      ]
     }
    }
   },
   {
    "event_id": "28352925-c86e-4720-80a5-99579bb28e4f",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 67,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "tool.responded",
    "node": "enrich",
    "payload": {
     "tool": "get_weather",
     "ok": true,
     "code": null,
     "elapsed_ms": 0,
     "args": {
      "lat": 37.5773694,
      "lng": 127.00575709999998,
      "date": "2026-11-21",
      "hours": [
       "19:30",
       "20:45",
       "21:30"
      ]
     }
    }
   },
   {
    "event_id": "e04d26cd-cfea-4618-8d20-d468da1b38df",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 68,
    "ts": "2026-11-20T10:07:04.526+09:00",
    "type": "node.exited",
    "node": "enrich",
    "payload": {
     "elapsed_ms": 1,
     "summary": "상위 5편",
     "ok": true
    }
   },
   {
    "event_id": "ca502afc-5c5b-4ee8-be90-0396cb16cdcd",
    "session_id": "s-demo",
    "run_id": "r-ddd9f96930",
    "seq": 1,
    "ts": "2026-11-20T10:07:04.527+09:00",
    "type": "run.started",
    "node": null,
    "payload": {
     "message": "1번 저장해줘"
    }
   },
   {
    "event_id": "1fbe0b0f-0638-47d4-ae5d-85fdf4590666",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 69,
    "ts": "2026-11-20T10:07:04.527+09:00",
    "type": "node.entered",
    "node": "respond",
    "payload": {}
   },
   {
    "event_id": "700ebcdd-e69c-4e47-bd2c-34c067950bbc",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 70,
    "ts": "2026-11-20T10:07:04.527+09:00",
    "type": "node.exited",
    "node": "respond",
    "payload": {
     "elapsed_ms": 0,
     "summary": null,
     "ok": true
    }
   },
   {
    "event_id": "3d54ffe3-eba6-4670-903d-1bd8086da2ab",
    "session_id": "s-demo",
    "run_id": "r-ee490a6b29",
    "seq": 71,
    "ts": "2026-11-20T10:07:04.527+09:00",
    "type": "run.completed",
    "node": null,
    "payload": {
     "elapsed_ms": 34,
     "status": "ok",
     "replan_count": 0,
     "llm_calls": 1,
     "api_calls": 27
    }
   },
   {
    "event_id": "8f085afb-4732-43eb-9ae6-b32a17ac229b",
    "session_id": "s-demo",
    "run_id": "r-ddd9f96930",
    "seq": 2,
    "ts": "2026-11-20T10:07:04.528+09:00",
    "type": "node.entered",
    "node": "analyze",
    "payload": {}
   },
   {
    "event_id": "29647dd1-c9ef-49fb-a817-19c6a8fc883b",
    "session_id": "s-demo",
    "run_id": "r-ddd9f96930",
    "seq": 3,
    "ts": "2026-11-20T10:07:04.528+09:00",
    "type": "llm.decision",
    "node": "analyze",
    "payload": {
     "kind": "intent",
     "value": "plan_save",
     "reason": "직전 추천 1번을 저장하라는 요청"
    }
   },
   {
    "event_id": "579f9569-8d67-461f-8025-87d81761011e",
    "session_id": "s-demo",
    "run_id": "r-ddd9f96930",
    "seq": 4,
    "ts": "2026-11-20T10:07:04.528+09:00",
    "type": "node.exited",
    "node": "analyze",
    "payload": {
     "elapsed_ms": 0,
     "summary": "plan_save",
     "ok": true
    }
   },
   {
    "event_id": "8ee72224-c02e-49bd-afe0-bcc4f34ff192",
    "session_id": "s-demo",
    "run_id": "r-ddd9f96930",
    "seq": 5,
    "ts": "2026-11-20T10:07:04.528+09:00",
    "type": "node.entered",
    "node": "save_plan",
    "payload": {}
   },
   {
    "event_id": "5475f893-74e3-4e2d-8f71-39e11277c09e",
    "session_id": "s-demo",
    "run_id": "r-ddd9f96930",
    "seq": 6,
    "ts": "2026-11-20T10:07:04.528+09:00",
    "type": "node.exited",
    "node": "save_plan",
    "payload": {
     "elapsed_ms": 0,
     "summary": "plan #1 · 겹침 0",
     "ok": true
    }
   },
   {
    "event_id": "f95aeafb-ef62-4634-b082-c5d96e127ac5",
    "session_id": "s-demo",
    "run_id": "r-ddd9f96930",
    "seq": 7,
    "ts": "2026-11-20T10:07:04.528+09:00",
    "type": "run.completed",
    "node": null,
    "payload": {
     "elapsed_ms": 1,
     "status": "ok",
     "replan_count": 0,
     "llm_calls": 1,
     "api_calls": 0
    }
   }
  ]
 }
};

(function () {
  const D = window.DEMO_DATA;
  let plans = JSON.parse(JSON.stringify(D.plans));
  let nextId = 100;
  const overlap = (a, b) => a.date === b.date && a.start_time < (b.end_time || b.start_time) && (a.end_time || a.start_time) > b.start_time;
  const withOverlaps = () => plans.map((p) => ({ ...p, overlaps: plans.filter((q) => q.id !== p.id && overlap(p, q)).map((q) => q.id) }));
  window.demoApi = async function (method, path, body) {
    await new Promise((r) => setTimeout(r, method === "POST" && path === "/api/chat" ? 700 : 80));
    if (path === "/api/health") return { status: "ok", services: { kopis: true, kakao: true, kma: true, llm: false } };
    if (path === "/api/chat") return D.chat;
    if (path === "/api/plans" && method === "GET") return { plans: withOverlaps() };
    if (path === "/api/plans" && method === "POST") {
      const plan = { ...body, id: nextId++, created_at: new Date().toISOString() };
      const overlaps = plans.filter((q) => overlap(plan, q));
      plans.push(plan);
      return { plan, overlaps };
    }
    const m = path.match(/^\/api\/plans\/(\d+)$/);
    if (m && method === "PATCH") { const p = plans.find((x) => x.id == m[1]); Object.assign(p, body); return { plan: p, overlaps: [] }; }
    if (m && method === "DELETE") { plans = plans.filter((x) => x.id != m[1]); return { deleted: true }; }
    if (path === "/api/logs") return { sessions: D.logs.sessions };
    if (path.startsWith("/api/logs/") && method === "GET") return { events: D.logs.events };
    if (path.startsWith("/api/logs/") && method === "DELETE") return { deleted: D.logs.events.length };
    throw { code: "NOT_FOUND", message: "예시 모드에서 지원하지 않는 요청이에요." };
  };
  window.DEMO_AUTOPLAY = function (renderReply, addMessage) {
    addMessage("user", D.chat.request);
    renderReply(D.chat);
  };
})();
