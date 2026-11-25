# Fauna Studio · Mac 개발용

동물 사진 한 장에서 종 후보를 찾고, 같은 종의 참고 사진을 비교하고, 선택한 사진으로 3D 모델을 만드는 로컬 데스크톱 프로그램입니다. 이 저장소는 [Windows 원본](https://github.com/HighDpsHotCat/fauna-studio)의 이력을 이어받은 Mac 개발용 저장소입니다.

## Mac에서 시작하기

Apple Silicon(M 시리즈) 맥북과 arm64 Python 3.11을 기준으로 구성했습니다. 현재 고정된 PyTorch 2.9.1의 macOS 패키지는 arm64용입니다. macOS 14 이상에서 시작하고, Blender 로우폴리 변환에는 해당 Mac에서 실행 가능한 Blender를 설치하세요. Python 3.10 환경도 실행기가 지원합니다.

터미널에서 다음 명령을 실행합니다.

```bash
git clone https://github.com/HighDpsHotCat/fauna-studio-mac.git
cd fauna-studio-mac
./run.command
```

첫 실행은 이 폴더의 `.venv`를 만들고 Python 패키지를 설치합니다. 이후에는 Finder에서 `run.command`를 더블 클릭하거나 같은 명령으로 실행할 수 있습니다. GitHub에서 ZIP으로 받았다면 먼저 `chmod +x run.command`를 실행하세요. 코드 수정 뒤 앱을 다시 열면 변경 내용이 적용됩니다.

Python 설치 경로가 다른 경우에는 `FAUNA_PYTHON=/opt/homebrew/bin/python3.11 ./run.command`처럼 지정할 수 있습니다. 이미 생성된 `.venv`가 있으면 그 환경을 재사용합니다. Python 아키텍처는 `python3.11 -c 'import platform; print(platform.machine())'`로 확인할 수 있으며 출력은 `arm64`여야 합니다.

Mac의 BioCLIP·TripoSR 연산은 CPU로 실행됩니다. 첫 사용 시 AI 모델 약 3.3 GB를 내려받으며 CPU 3D 생성 시간은 사진과 Mac 사양에 따라 달라집니다. Apple GPU를 사용하는 MPS 최적화는 이후 개발 항목입니다. Blender는 `/Applications/Blender.app` 또는 `~/Applications/Blender.app`에서 자동으로 찾습니다. 다른 위치에 설치했다면 앱의 **Blender 실행 파일 선택…**에서 `Blender.app` 폴더를 지정하세요.

## Mac 개발 확인

의존성을 설치한 가상 환경에서 다음 명령으로 화면 생성, TripoSR 작업 프로세스 실행·취소, Blender 앱 경로, 예제 GLB 뷰어 서버를 확인합니다.

```bash
.venv/bin/python -m unittest discover -s tests -v
```

GitHub Actions에서도 Mac arm64와 Windows에서 이 검사를 실행합니다. AI 가중치를 사용하는 실제 종 분류·3D 생성, Blender 실행, 브라우저의 회전·확대 조작은 맥북에서 다음 순서로 확인하세요.

1. `./run.command`로 앱을 열고 예제 사진으로 종 분류와 커먼스 검색을 실행합니다.
2. 원본 사진에서 3D 모델을 생성해 한글·공백이 있는 경로에 저장합니다.
3. **로우폴리로 변환…**에서 목표 삼각형 수를 3,000으로 정해 별도 GLB를 저장합니다.
4. 두 GLB를 **3D 뷰어로 열기**에서 열어 회전과 확대·축소를 확인합니다.

`examples/`의 GLB를 사용하면 AI 모델 다운로드 전에 Blender와 뷰어를 확인할 수 있습니다.

## Windows 실행 파일

설치 파일을 빌드하면 `dist/FaunaStudio-Setup-x64.exe`가 생성됩니다. 이 파일을 더블 클릭하면 사용자 계정에 설치한 뒤 앱이 열립니다. 다음부터는 Windows 시작 메뉴에서 **Fauna Studio**를 실행하세요. 설치 파일 하나를 다른 Windows 10/11 x64 PC로 복사할 수 있습니다. GitHub에서 소스를 내려받았다면 아래 실행 방법을 따르세요.

Python, Qt, Three.js와 CPU·NVIDIA CUDA용 추론 라이브러리가 포함되어 있습니다. 최초 설치에는 약 6 GB의 여유 공간이 필요합니다. AI 모델은 처음 사용할 때 약 3.3 GB를 추가로 내려받습니다. 커먼스 사진 검색에는 인터넷 연결이 필요하고, 로우폴리 변환에는 Blender 설치가 필요합니다.

설치 위치는 사용자 계정의 로컬 앱 데이터 폴더 아래 FaunaStudio입니다. 설치 파일을 지운 뒤에도 설치된 앱은 실행됩니다. 앱을 제거하려면 종료 후 해당 설치 폴더와 시작 메뉴의 Fauna Studio 바로 가기를 삭제하세요.

## Windows에서 소스 실행

Windows PowerShell에서 프로젝트를 복제합니다. Git, 64비트 Python 3.10과 Windows Python 실행기(`py`)를 준비하세요. 로우폴리 변환에는 Blender도 설치해야 합니다.

```powershell
git clone https://github.com/HighDpsHotCat/fauna-studio-mac.git
cd fauna-studio-mac
.\run.cmd
```

1. 이 폴더에서 **run.cmd**를 더블 클릭합니다. 새 PC에는 64비트 Python 3.10과 Windows Python 실행기(`py`)가 필요합니다.
2. **사진 열기**로 JPG, PNG, WEBP 파일을 선택하거나 창에 끌어 놓습니다. **이 사진으로 분류하기**를 누르면 함께 제공된 붉은여우 사진으로 시작합니다.
3. 첫 번째 후보의 참고 사진이 자동으로 열립니다. 왼쪽 후보를 누르면 해당 종의 사진으로 바뀝니다.
4. 사진 아래 **원문 열기**를 누르면 저자, 라이선스 조건, 원본 파일을 커먼스에서 확인할 수 있습니다.

첫 실행 시 실행기가 프로젝트의 `.venv`에 패키지를 설치합니다. 처음 분류할 때 Hugging Face에서 모델과 분류 데이터를 약 1.45 GB 받아 사용자 캐시에 보관합니다. 이후 분류는 오프라인에서도 작동합니다. 사진 검색과 미리보기에는 인터넷 연결이 필요합니다.

배포 파일을 다시 만들 때는 CUDA가 포함된 프로젝트 가상 환경에서 `.venv\Scripts\python.exe packaging\build_windows.py`를 실행합니다. 빌드에는 Windows의 .NET Framework 4.x C# 컴파일러와 Visual Studio C++ x64 재배포용 CRT가 필요합니다.

## 함께 개발하기

`main`에서 작업용 브랜치를 만들고 변경 사항을 커밋한 뒤 Pull Request로 합칩니다. Collaborator 초대를 수락하면 이 저장소에 브랜치를 올릴 수 있습니다. 초대 전에는 GitHub의 Fork 기능으로 본인 계정에 복사해 작업할 수 있습니다.

| 파일 | 역할 |
| --- | --- |
| `app.py`, `ui.py` | 데스크톱 화면과 작업 연결 |
| `classifier.py`, `commons.py` | BioCLIP 종 분류와 위키미디어 사진 검색 |
| `mesh_panel.py`, `mesh_worker.py` | TripoSR 실행과 GLB 저장 |
| `lowpoly_dialog.py`, `blender_lowpoly.py` | 목표 삼각형 수 입력과 Blender 변환 |
| `web_viewer.py`, `viewer/` | 로컬 HTTP 서버와 Three.js 뷰어 |
| `packaging/` | Windows 설치 파일 빌드 |

변경 후 Mac에서는 `run.command`, Windows에서는 `run.cmd`로 실행하여 관련 기능을 확인하세요. `assets/red-fox.jpg`로 분류·3D 생성을 확인하고, `examples/`의 GLB로 로우폴리 변환과 뷰어를 확인할 수 있습니다. 작업 환경과 배포 결과물은 `.gitignore`에서 관리합니다. 예제 이미지·모델의 출처와 라이선스는 아래에, 포함된 외부 코드의 라이선스는 각 `vendor` 폴더에 있습니다.

## 3D 생성과 저장

1. 왼쪽 입력 사진 아래 **원본으로 3D 생성…**을 누르거나, 커먼스 사진 카드의 **이 사진으로 3D 생성…**을 누릅니다. 원본은 종 분류를 기다리지 않고 선택할 수 있습니다.
2. 저장할 **.glb** 파일 이름과 위치를 정합니다. TripoSR이 선택한 사진 한 장으로 표면과 정점 색상을 생성합니다. 투명 배경은 그대로 사용하고, 일반 사진은 U²-Net으로 배경을 분리합니다.
3. 완료되면 **저장 폴더 열기**를 누릅니다. GLB 하나에 메시, 정점 색상, 원본 사진 정보가 들어갑니다. 커먼스 사진에는 원문 주소, 저자, 라이선스 이름도 들어갑니다. 생성 중 **생성 취소**를 누르면 기존 대상 파일을 보존합니다.

처음에는 TripoSR 가중치 약 1.68 GB와 일반 사진의 배경 분리 가중치 약 176 MB를 내려받습니다. 이후 로컬 사진으로 오프라인 생성이 가능합니다. 커먼스 사진을 선택하면 해당 파일의 최대 너비 1,280픽셀 이미지를 인터넷에서 받습니다. CUDA를 사용할 수 있으면 GPU로 생성하고, CUDA를 사용할 수 없거나 GPU 메모리가 부족하면 CPU로 생성합니다. 동물 한 마리의 전신이 뚜렷한 사진이 적합하며, 사진에 가려진 면은 모델이 추정합니다. [TripoSR 모델](https://huggingface.co/stabilityai/TripoSR)

공식 TripoSR 추론 코드의 리비전 107cefdc244c39106fa830359024f6a2f1c78871을 vendor/triposr에 포함했습니다. Windows에서 컴파일 없이 실행하도록 표면 추출에 scikit-image를 사용하고, 이미지 인코더의 설정을 로컬 캐시에서 읽습니다. 원본 코드의 라이선스와 저작권 고지는 해당 폴더에 있습니다. [TripoSR 원본 코드](https://github.com/VAST-AI-Research/TripoSR/tree/107cefdc244c39106fa830359024f6a2f1c78871)

## Blender 로우폴리 변환

1. 3D 생성 완료 후 **로우폴리로 변환…**을 누릅니다. 이전에 저장한 GLB는 상단 **로우폴리 변환… → GLB 선택…**으로 열거나 앱 창에 끌어 놓습니다.
2. 원본의 삼각형 수를 확인하고 **목표 삼각형 수**를 입력합니다. 기본값은 **3,000개**입니다.
3. **변환하여 별도 GLB 저장…**을 눌러 새 파일의 위치를 선택합니다. 완료 화면에서 실제 삼각형 수를 확인하거나 저장 폴더를 열 수 있습니다.

변환은 설치된 Blender를 백그라운드에서 실행합니다. Mac의 Applications 폴더, Windows 표준 설치 폴더와 PATH에서 실행 파일을 찾습니다. 다른 설치 위치는 **Blender 실행 파일 선택…**으로 지정할 수 있습니다. Windows 원본은 Blender 5.2.2 LTS로 검증했습니다. [Blender 다운로드](https://www.blender.org/download/)

목표값은 모델 전체의 삼각형 예산입니다. Blender가 모서리를 합치는 과정에서 정확한 개수가 불가능하면 목표 이하의 가까운 결과를 저장합니다. 원본이 이미 목표 이하이면 동일한 GLB를 선택한 새 위치에 복사합니다. 정점 색상과 원본 사진의 출처 정보도 로우폴리 GLB에 보관됩니다.

## 로컬 3D 웹 뷰어

앱 상단의 **3D 뷰어…**에서 GLB를 선택하면 기본 브라우저에서 바로 열립니다. TripoSR 생성이나 Blender 변환을 막 끝냈다면 저장 완료 화면에서 **3D 뷰어로 열기**를 누르세요. 뷰어 안의 **GLB 열기…**로 다른 모델로 전환할 수 있습니다.

- **회전**은 마우스 드래그 또는 한 손가락 드래그를 사용합니다.
- **확대·축소**는 휠, 두 손가락 핀치 또는 화면 아래 **+ / −** 버튼으로 조작합니다.
- **화면 맞춤**은 모델 전체가 보이는 처음 시점으로 돌아갑니다. 모델 화면에 키보드 초점을 두면 방향키, + / −, Home 키도 사용할 수 있습니다.

뷰어는 앱이 실행되는 동안 이 PC의 127.0.0.1에서 동작합니다. Three.js 0.187.0과 GLB 로더를 앱에 포함해 인터넷 연결 없이 사용할 수 있습니다. WebGL 2를 지원하는 브라우저가 필요합니다. [Three.js](https://threejs.org/) · [포함된 라이선스](viewer/vendor/three/LICENSE)

## 분류와 검색

- 원본 BioCLIP 이미지 인코더와 TreeOfLife-10M의 공개 텍스트 임베딩을 사용합니다. 동물계의 이명법 학명에 해당하는 항목을 비교하고 같은 학명의 점수를 합산해 상위 다섯 후보를 표시합니다. 점수는 모델의 상대 점수이며, 사람의 종 동정 정확도를 뜻하지 않습니다. [BioCLIP](https://github.com/Imageomics/bioclip) · [분류 데이터](https://huggingface.co/datasets/imageomics/TreeOfLife-10M)
- 입력한 사진은 PC 안에서 처리합니다. 검색할 때 위키데이터의 학명(P225)을 대조한 뒤 커먼스의 묘사 대상(P180) 태그 또는 해당 종의 카테고리로 사진을 최대 12장 찾습니다. 옛 학명이 현재 분류군과 명시적으로 연결되어 있으면 검색 화면에 두 이름을 함께 표시합니다. [커먼스 구조화 데이터](https://commons.wikimedia.org/wiki/Commons:Structured_data) · [위키데이터의 원래 학명 연결](https://www.wikidata.org/wiki/Property:P12765)
- 검색 결과는 커먼스 기여자가 남긴 태그와 분류에 따릅니다. 파일 형식과 제목·카테고리로 지도나 삽화 등을 걸러내지만 오분류된 파일이 섞일 수 있습니다. 사진 수는 종마다 다릅니다.
- 기본 설치는 CPU에서 작동합니다. 프로젝트 환경에 CUDA를 지원하는 PyTorch가 설치되어 있으면 CUDA를 사용합니다. 분류가 완료되면 창 오른쪽 위에서 실제 사용 장치를 확인할 수 있습니다.

## 예제 사진과 모델

**Vulpes vulpes Mallnitz 01.jpg** · Uoaei1 촬영. 커먼스에서 제공하는 960픽셀 축소본을 포함했습니다. [파일 원문](https://commons.wikimedia.org/wiki/File:Vulpes_vulpes_Mallnitz_01.jpg) · [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)

함께 제공하는 붉은여우 GLB는 이 사진을 TripoSR로 재구성한 예제입니다. 동일한 CC BY-SA 4.0으로 제공합니다. [예제 모델](examples/red-fox.glb)

같은 모델을 Blender로 줄인 3,000개 삼각형 버전도 포함했습니다. [붉은여우 로우폴리 GLB](examples/red-fox-lowpoly-3000.glb)
