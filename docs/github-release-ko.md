# GitHub Release 배포 가이드

## 배포 자산

```bash
python3 scripts/build_release.py
(cd dist && sha256sum -c SHA256SUMS)
```

생성 파일:

- `dist/ranwiki-v0.1.0.zip`
- `dist/SHA256SUMS`

ZIP은 allowlist 방식으로 생성되며 `data`, SQLite DB, `.env`, `config.yaml`, `.devdeps`, Git metadata와 credential을 포함하지 않는다.

## 최초 GitHub 저장소 생성

저장소 공개 여부는 사용자가 결정한다. 내부 repository 주소나 조직 정보가 소스/문서에 포함되는 경우 private 저장소를 권장한다.

GitHub CLI 인증:

```bash
gh auth login -h github.com
gh auth status
```

로컬 Git 저장소가 아직 없다면:

```bash
git init
git add .
git status
git commit -m "Release RAN Wiki v0.1.0"
git branch -M main
```

private 저장소 예시:

```bash
gh repo create ranwiki --private --source=. --remote=origin --push
```

public으로 공개하려면 소스와 문서에 내부 주소, 조직 정보, credential이 없는지 별도로 검토한 후 `--public`을 사용한다.

## 태그와 Release 게시

```bash
git tag -a v0.1.0 -m "RAN Wiki v0.1.0"
git push origin v0.1.0
gh release create v0.1.0 \
  dist/ranwiki-v0.1.0.zip \
  dist/SHA256SUMS \
  --title "RAN Wiki v0.1.0" \
  --notes-file docs/release-notes-v0.1.0.md
```

게시 후 확인:

```bash
gh release view v0.1.0
gh release download v0.1.0 --dir /tmp/ranwiki-release-check
(cd /tmp/ranwiki-release-check && sha256sum -c SHA256SUMS)
unzip -t /tmp/ranwiki-release-check/ranwiki-v0.1.0.zip
```

## 새 버전 배포

`pyproject.toml`의 version과 릴리스 노트 파일을 먼저 갱신하고 테스트 후 다시 빌드한다. 이미 게시한 동일 태그의 ZIP을 조용히 교체하지 않는다. 내용이 바뀌면 새 버전 태그를 만든다.
