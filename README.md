# 미국 주식 리포트 사이트

이 폴더는 Codex 자동화가 생성하는 미국장 시황/추천 점검 HTML 리포트를 정적 웹사이트로 배포하기 위한 루트입니다.

현재 배포 방식:

1. 이 폴더는 `ELLOIZE/Stock` 저장소에 연결되어 있습니다.
2. GitHub Pages는 `gh-pages` 브랜치의 루트 폴더를 서빙합니다.
3. 자동화가 `reports/YYYY-MM-DD.html`을 생성하고 `index.html`에 새 링크를 추가합니다.
4. 자동화는 변경 사항을 커밋한 뒤 `main`과 `gh-pages` 브랜치에 push합니다.
5. Gmail에는 전체 리포트 대신 공개 URL 요약 링크를 보냅니다.

TradingView 위젯은 Gmail 본문에서는 차단되지만, GitHub Pages 같은 브라우저 페이지에서는 작동합니다.
