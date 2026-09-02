from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from pathlib import Path
from time import sleep
from random import randrange
import os;import subprocess;import re;import json

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(__file__).resolve().parent / "downloads"
SETTINGS:dict

def getSettings(file_path)->dict[str:str]:
    path = Path(file_path)

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("id=\npass=", encoding="utf-8") # 여기 바꾸기
        print(f"로그인 정보 확인 안됨\n{file_path} 파일에\nid=<id>\npass=<pass>\n로 작성해주세요")
        raise

    lines = path.read_text(encoding="utf-8").splitlines()

    data = {}
    for line in lines:
        l = line.split("=")
        if len(l)!=2:
            continue
        a,b = l
        if b.lower() == "true" or b.lower()=="false":
            data[a] = True if b=="True" else False
        else:
            data[a]=b
            pass
    kyz = data.keys()
    if "id" in kyz and "pass" in kyz and data["id"]!=None and data["pass"]!=None:
        return data
    def checkThis(key:str,typ:type=bool,default=False):
        if key not in kyz or type(data[key])!=typ:
            data[key] = default
        pass
    checkThis("skipcheck")
    checkThis("download")
    checkThis("manualInput")
    checkThis("ffmpegloc",str,"ffmpeg")
    checkThis("visibleHeader")
    print(f"오류!\n{file_path} 파일에\nid:<id>\npass:<pass>\n로 작성해주세요")
    raise
SETTINGS = getSettings(str((SCRIPT_DIR / "settings.txt").resolve()))

def getNplayTodayVids():
    options = webdriver.ChromeOptions()
    options.add_argument("--log-level=3")
    if not SETTINGS["visibleHeader"]:
        options.add_argument("--headless=new");
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    print("홈피 여는중")
    driver.get("https://learn.inha.ac.kr/login.php")
    driver.implicitly_wait(10)
    ID = SETTINGS["id"];PASS = SETTINGS["pass"]
    #driver.find_element(By.NAME, "username").click()
    driver.find_element(By.NAME, "username").send_keys(ID)
    driver.find_element(By.NAME, "password").send_keys(PASS)
    driver.find_element(By.NAME, "loginbutton").click()
    print("로그인 완료")
    
    if SETTINGS["manualInput"]:
        print("manualInput 세팅이 True로 되어있습니다.\n자동시청할 영상id들을 입력해주세요\n>",end="")
        tottime = 0
        for vidid in input().split():
            tme = openVid(driver,vidid,download=SETTINGS["download"])
            tottime+=tme
        print(f"시청 완료! 걸린시간 - {tottime//3600}:{(tottime//60)%60:02d}:{tottime%60:02d}")
        return
    
    print("이번 주차의 강의 검색중..")
    toview = driver.find_elements(By.CSS_SELECTOR,"ul.my-course-lists.coursemos-layout-0 li div a")
    vidDatas = dict()
    tottime = 0
    for view in toview:
        cosid = view.get_property("href").split("=")[1]
        driver.execute_script(f"window.open('https://learn.inha.ac.kr/course/view.php?id={cosid}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        ky = driver.find_element(By.CSS_SELECTOR,".coursename a").text.split("[")[0]
        print(f"{ky} 검색중...")
        vidDatas[ky]=[]
        driver.implicitly_wait(1)
        vididcss = driver.find_elements(By.CSS_SELECTOR,".course_box.course_box_current ul li div:nth-child(4) ul li.activity.vod div div div:nth-child(2) div a")
        driver.implicitly_wait(10)
        if len(vididcss) == 0: # 없는지 확인
            driver.close()
            driver.switch_to.window(driver.window_handles[-1])
            continue
        
        ju = driver.find_element(By.CSS_SELECTOR,".course_box.course_box_current .content .sectionname a")
        ju = int(ju.text.split("주")[0])
        driver.execute_script(f"window.open('https://learn.inha.ac.kr/report/ubcompletion/user_progress_a.php?id={cosid}', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        mains = driver.find_elements(By.CSS_SELECTOR,".table.table-bordered.user_progress_table tbody tr:has(> :nth-child(6)) >td:first-child")
        cumul = 1;dc = 0
        for main in mains:
            if main.get_attribute("rowspan") == None:
                break
            if int(main.text)==ju:
                dc = int(main.get_attribute("rowspan"))
                break
            cumul += int(main.get_attribute("rowspan"))
            pass
        watchcheck = ", ".join([f".user_progress_table tbody tr:nth-child({i}):has(>:nth-child(6))>:nth-child(5),.user_progress_table tbody tr:nth-child({i}):not(:has(> :nth-child(5))) > :nth-child(4)" for i in range(cumul,cumul+dc)])
        watched = []
        if watchcheck != "":
            watchcheck = driver.find_elements(By.CSS_SELECTOR,watchcheck)
            for watch in watchcheck:
                if watch.text == "X":
                    watched.append(False)
                elif watch.text == "O":
                    watched.append(True)
                else:
                    watched.append(None)
                pass
        driver.close()
        driver.switch_to.window(driver.window_handles[-1])
        for vid in vididcss:
            vidDatas[ky].append({"id":vid.get_property("href").split("id=")[1]})
        for i,vid in enumerate(driver.find_elements(By.CSS_SELECTOR,".course_box.course_box_current ul li div:nth-child(4) ul li.activity.vod .instancename")):
            vidDatas[ky][i]["name"]=vid.text[:-4]
            if len(watched) > i:
                vidDatas[ky][i]["required"]=not watched[i]
            else:
                vidDatas[ky][i]["required"]=None
        for i,vid in enumerate(driver.find_elements(By.CSS_SELECTOR,".course_box.course_box_current ul li div:nth-child(4) ul li.activity.vod .text-info")):
            tme=vid.text.lstrip(", ")
            vidDatas[ky][i]["length"] = tme
            if vidDatas[ky][i]["required"]:
                tottime += int(tme.split(":")[0])*60+int(tme.split(":")[1])
            pass
        driver.close()
        driver.switch_to.window(driver.window_handles[-1])
        pass
    #print(vidDatas)
    print("================================================================================")
    print(f"<{ju}주차>")
    for key,val in vidDatas.items():
        print(f"{key}")
        if len(val)==0:
            print("- 영상 없음")
            continue
        for vid in val:
            print(f"- {vid['name']} ({vid['length']}) / {'시청필요' if vid['required'] else ('시청불필요' if vid['required']==None else '시청완료')}")
            pass
        pass
    print(f"자동시청 예상 시간 - {tottime//3600}:{(tottime//60)%60:02d}:{tottime%60:02d}")
    print("================================================================================")
    if not SETTINGS["skipcheck"]:
        x = input("엔터 키를 눌러서 자동시청합니다.\n'X' 를 입력하여 취소하세요")
        if x.lower() == "x":
            return
        pass
    
    tottime = 0
    for key,val in vidDatas.items():
        for vid in val:
            if vid['required']==True:
                print(f"{'다운로드 & ' if SETTINGS['download'] else ''}시청 - {vid['name']}")
                tme = openVid(driver,vid['id'],vid['name'],download=SETTINGS['download'])
                tottime+=tme
            elif SETTINGS['download']:
                print(f"다운로드 - {vid['name']}")
                openVid(driver,vid['id'],vid['name'],download=True,watch=False)
        pass
    print(f"시청 완료! 걸린시간 - {tottime//3600}:{(tottime//60)%60:02d}:{tottime%60:02d}")
    return

def sanitize_filename(name, max_length=100):
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip().replace(" ", "_")
    return name[:max_length]

def format_time(seconds):
    minutes = int(seconds) // 60
    seconds = int(seconds) % 60
    return f"{minutes:02}:{seconds:02}"

def progressTimer(duration, bar_width=40):
    elapsed = 0
    while True:
        
        if elapsed >= duration:
            elapsed = duration
            finished = True
        else:
            finished = False

        # Calculate progress
        progress = elapsed / duration
        filled = int(progress * bar_width)
        prec = int(progress*1000)/10
        # Build the bar
        bar = "=" * filled + " " * (bar_width - filled)

        elapsed_text = format_time(elapsed)
        duration_text = format_time(duration)

        print(f"\r[{bar[:bar_width//2]}({elapsed_text}/{duration_text}){bar[bar_width//2:]}] ({prec}%)",end="")
        if finished:
            break
        elapsed+=1
        sleep(1)
        pass
    print()  # Move to the next line when finished
    pass

def openVid(driver:webdriver.Chrome,vidid,vidtitle,download=False,watch=True):
    driver.execute_script(f"window.open('https://learn.inha.ac.kr/mod/vod/viewer.php?id={str(vidid)}', '_blank');")
    driver.switch_to.window(driver.window_handles[1])
    sleep(1)
    try:
        driver.switch_to.alert.dismiss()
    except:
        pass
    if download:
        filename = sanitize_filename(f"{vidtitle}.mp4")
        os.makedirs(str(OUTPUT_DIR.resolve()), exist_ok=True)
        outPath = str(OUTPUT_DIR.resolve())+"/"+filename
        src = driver.find_element(By.CSS_SELECTOR, "#my-video_html5_api").get_attribute("data-setup-lazy")
        src = json.loads(src)["sources"]["src"]
        #print(SETTINGS["ffmpegloc"],"\n",src,"\n",outPath)
        cmd = [
            SETTINGS["ffmpegloc"],
            "-headers",
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Safari/537.36\r\n',
            "-i", src,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            outPath
        ]
        process = subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        pass
        
    tme = driver.find_element(By.CSS_SELECTOR,"span.playtime").text
    sec = int(tme.split(":")[0])*60+int(tme.split(":")[1])
    watchtime = sec+100+randrange(80)
    if watch:
        driver.find_element(By.CSS_SELECTOR, "button.vjs-big-play-button").click()
        driver.find_element(By.CSS_SELECTOR, "button.vjs-mute-control.vjs-control.vjs-button.vjs-vol-3").click()
        print(f"{watchtime//3600}:{(watchtime//60)%60:02d}:{watchtime%60:02d}")
        progressTimer(watchtime)
    driver.close()
    driver.switch_to.window(driver.window_handles[0])
    if download:
        process.wait() # hoxy 다운 안끝났을수도
    return watchtime

getNplayTodayVids()
input("엔터 키를 눌러서 종료합니다.")