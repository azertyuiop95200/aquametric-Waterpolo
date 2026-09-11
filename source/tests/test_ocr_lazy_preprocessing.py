import numpy as np
import cv2
import services.scoreboard_ocr as ocr


def test_readable_first_pass_avoids_unneeded_filters(monkeypatch):
    monkeypatch.setattr(ocr, 'tesseract_available', lambda: True)
    monkeypatch.setattr(ocr, '_ocr_once', lambda *a: ('Q1 7:30 2 1', .91))
    def unnecessary(*args, **kwargs):
        raise AssertionError('Fallback filter executed despite successful primary OCR')
    monkeypatch.setattr(cv2, 'bilateralFilter', unnecessary)
    assert ocr.ocr_image(np.zeros((60,200,3),dtype=np.uint8)) == ('Q1 7:30 2 1', .91)


def test_fallback_pixels_and_result_are_unchanged(monkeypatch):
    image=np.random.default_rng(7).integers(0,256,(40,130,3),dtype=np.uint8)
    enlarged=cv2.resize(image,None,fx=2,fy=2,interpolation=cv2.INTER_CUBIC)
    gray=cv2.cvtColor(enlarged,cv2.COLOR_BGR2GRAY)
    clahe=cv2.createCLAHE(clipLimit=2.3,tileGridSize=(8,8)).apply(cv2.bilateralFilter(gray,7,45,45))
    otsu=cv2.threshold(clahe,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    expected=[enlarged,clahe,otsu]
    seen=[]
    monkeypatch.setattr(ocr,'tesseract_available',lambda:True)
    def recognize(img,*args):
        np.testing.assert_array_equal(img,expected[len(seen)])
        seen.append(img)
        return [('noise',.1),('Q2 6:20 3 2',.8),('Q2 6:20 3 2',.7)][len(seen)-1]
    monkeypatch.setattr(ocr,'_ocr_once',recognize)
    assert ocr.ocr_image(image)==('Q2 6:20 3 2',.8)
    assert len(seen)==3


def test_reused_live_frame_ocr_keeps_each_observation(monkeypatch):
    from types import SimpleNamespace
    import services.live_frame_match_analysis as live
    monkeypatch.setattr(live,'tesseract_available',lambda:True)
    monkeypatch.setattr(live,'_ocr_plan',lambda *a:[1.,2.])
    monkeypatch.setattr(live,'_nearest_record',lambda *a:{'index':1,'path':'frame.jpg'})
    monkeypatch.setattr(live.cv2,'imread',lambda *a:np.zeros((100,100,3),dtype=np.uint8))
    calls=[]
    def recognize(image):
        calls.append(1)
        return 'Q1 7:30 2 1',.91
    monkeypatch.setattr(live,'ocr_image',recognize)
    observations,meta=live._focused_ocr_from_live_frames([{'index':1}], [SimpleNamespace(x=0,y=0,w=1,h=1,name='score')],source_duration=60,playback_rate=1,segments=1,moments=[],max_samples=2)
    assert len(calls)==1
    assert [x['second'] for x in observations]==[1.,2.]
    assert all(x['raw_text']=='Q1 7:30 2 1' for x in observations)
