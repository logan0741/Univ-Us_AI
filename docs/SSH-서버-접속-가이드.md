# Jupyter 서버 SSH 접속 가이드

## 서버 정보

| 항목 | 값 |
|------|-----|
| 호스트 | `168.131.30.102` |
| 포트 | `32468` |
| 계정 | `jovyan` |
| 인증 방식 | **키(pem) 인증 전용 — 비밀번호 없음** |

> ⚠️ 접속 중 비밀번호를 물어본다면, 비밀번호가 있는 게 아니라 **키 인증이 실패한 것**입니다.
> 아래 [문제 해결](#문제-해결)을 확인하세요.

## 준비물

- `private.pem` 파일 — 팀원에게 **안전한 경로**(사내 메신저 DM, USB 등)로 전달받으세요.
  절대 git 커밋, 공개 채널, 이메일 첨부로 공유하지 마세요. (이 저장소는 `.gitignore`에 `*.pem`이 등록되어 있습니다.)

---

## Windows 설정

### 1. 키 파일 저장

`private.pem`을 `C:\Users\<사용자명>\.ssh\private.pem` 에 저장합니다.
(`.ssh` 폴더가 없으면 만드세요.)

### 2. 키 파일 권한 잠그기 (필수!)

PowerShell에서 실행:

```powershell
icacls "$env:USERPROFILE\.ssh\private.pem" /inheritance:r /grant:r "${env:USERNAME}:R"
```

> Windows OpenSSH는 키 파일이 다른 사용자에게도 열려 있으면
> `UNPROTECTED PRIVATE KEY FILE` 경고와 함께 키를 **조용히 무시**하고 비밀번호를 물어봅니다.
> 이 단계를 건너뛰는 것이 "비번 치라고 나오는" 문제의 가장 흔한 원인입니다.

### 3. SSH config 등록

`C:\Users\<사용자명>\.ssh\config` 파일에 아래 내용을 추가합니다 (파일이 없으면 새로 생성, 확장자 없음):

```
Host jupyter-server
    HostName 168.131.30.102
    Port 32468
    User jovyan
    IdentityFile ~/.ssh/private.pem
    IdentitiesOnly yes
```

### 4. 접속 테스트

```powershell
ssh jupyter-server
```

비밀번호 입력 없이 바로 셸이 열리면 성공입니다.

---

## macOS / Linux 설정

```bash
mkdir -p ~/.ssh
mv ~/Downloads/private.pem ~/.ssh/private.pem
chmod 600 ~/.ssh/private.pem
```

`~/.ssh/config`에 Windows와 동일한 Host 블록을 추가한 뒤 `ssh jupyter-server`로 테스트합니다.

---

## VS Code Remote-SSH로 접속

1. VS Code 확장 **Remote - SSH** 설치 (ms-vscode-remote.remote-ssh)
2. 좌측 하단 `><` 아이콘 클릭 → **Connect to Host...** (또는 `F1` → `Remote-SSH: Connect to Host...`)
3. **jupyter-server** 선택
4. 플랫폼을 물어보면 **Linux** 선택
5. 접속 후 `File > Open Folder` → `/home/jovyan` 열기

---

## 문제 해결

### "비밀번호를 입력하라고 나와요"

이 서버에는 비밀번호가 없습니다. 키 인증이 실패한 것이므로 순서대로 확인:

1. `~/.ssh/config`에 `jupyter-server` 블록이 있고 `IdentityFile` 경로가 실제 pem 위치와 일치하는지
2. (Windows) 위의 `icacls` 권한 명령을 실행했는지
3. (macOS/Linux) `chmod 600`을 했는지
4. `ssh -v jupyter-server` 출력에서 `Trying private key: ...private.pem` 줄이 보이는지 — 안 보이면 config 경로 문제

### "Permission denied (publickey)"

- 키 파일이 올바른지 확인: `ssh-keygen -l -f <pem경로>` 실행 시 지문이
  `SHA256:47GWpgyFwAzAAg9lmI6G/tsIGtEgcFEtGxWUYBhIgfU` 인지 확인 (다르면 잘못된 키)
- 지문이 맞는데도 거부되면 서버 쪽 등록 문제 → 관리자에게 문의

### "UNPROTECTED PRIVATE KEY FILE" 경고

키 파일 권한이 열려 있는 것 → 위 2단계(권한 잠그기) 실행

### 서버(Jupyter pod)가 재시작된 후 접속이 안 될 때

pod가 재생성되면 등록된 공개키가 초기화될 수 있습니다.
Jupyter 웹 UI에서 Terminal을 열고 아래를 실행해 공개키를 재등록하세요:

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCo0ras5cGK49kSloz3yxuZ1VjBmBTNeFAFqF+FEgdzYnaGyqblzkC5+yfuOMIpMNr1vgZ0s8nkzTbqx4sY3Zp8yS0F2GRPm7v76HtLSgOc5TheHl6GBpuSSZe1fCrP3jDN9pD/Ku1qEHwE25SMtniLnSam4m6IT9dkMN/afWBBxysQ6h+0Mhb2l5YaswAQUUo8quhq8+aZuKU773nOGH18XN2W3SN4HkwVlMRchxnxByop0EzRQgs9sU3+zfv5bTaiGV3eb4mwRcmLqpwv3QwLDy5WDyWJOJWzLlKMmUfjQSLhIy4EuiD3ZDczBFJCjQYJD2kQEVlZP2vSRU559BMx' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

---

## (권장) 개인 키로 접속하기 — pem 공유 없이

pem 하나를 모두가 공유하는 대신, 각자 자기 키를 등록하는 방식이 더 안전합니다:

1. 개발자 본인 PC에서 키 생성:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_jupyter
   ```
2. 생성된 **공개키**(`~/.ssh/id_ed25519_jupyter.pub` 내용)를 기존 접속 가능한 사람에게 전달
3. 전달받은 사람이 서버에서 등록:
   ```bash
   echo '<전달받은 공개키 한 줄>' >> ~/.ssh/authorized_keys
   ```
4. 개발자는 config의 `IdentityFile`을 자기 키로 지정해 접속

이렇게 하면 pem 파일을 돌려쓸 필요가 없고, 특정 개발자의 접근만 개별적으로 회수할 수도 있습니다.
