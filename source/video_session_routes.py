from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")

CHAPTERS = [
 {"title":"Duel & contact physique","focus":"Micro-technique","intro":"Comprendre comment l'avantage se crée avant que la lutte soit visible.","observe":["Inside water et position des hanches","Épaule/avant-bras de contrôle sans pousser inutilement","Premier puis deuxième contact","Changement de rythme au moment du déséquilibre"],"questions":["Qui possède l'axe ballon-but ?","Quelle joueuse sent le déplacement adverse en premier ?","À quel instant les hanches passent devant ?"]},
 {"title":"Jeu sans ballon & séparation","focus":"Timing","intro":"Créer la réception plutôt qu'attendre d'être libre.","observe":["Slow-fast, stop-go, contre-mouvement","Séparation synchronisée avec le départ de passe","Drive utile même sans réception","Replacement après drive"],"questions":["Le mouvement crée-t-il un avantage pour elle ou une partenaire ?","La passe part-elle avant ou après l'ouverture ?"]},
 {"title":"Centre / centre-back","focus":"Duel intérieur","intro":"Lire le seal, re-seal, front, 3/4 et les aides autour du centre.","observe":["Seal et reverse seal","Spin et step-out","Front/re-front selon la position du ballon","Timing de la deuxième défenseure"],"questions":["Qui contrôle les hanches ?","La centre peut-elle recevoir et finir dans le même mouvement ?","D'où doit venir l'aide ?"]},
 {"title":"Passe clé & manipulation","focus":"Ball movement","intro":"Identifier la passe qui crée l'avantage, pas seulement l'assist final.","observe":["Passe devant / extérieure / haute / lob","Skip pass et one-more","Fake avant passe","Pass 0, +1 et +2"],"questions":["Quelle passe a réellement déplacé la défense ?","La réception permet-elle une action immédiate ?"]},
 {"title":"Lecture avant réception","focus":"Game IQ","intro":"Montrer les informations acquises avant que le ballon arrive.","observe":["Scan centre-gardienne-aide","Faux regard","Lecture du bras dominant","Chronomètre et score"],"questions":["Que savait déjà la joueuse à T−1 ?","Quelle information déclenche sa décision ?"]},
 {"title":"M-zone & défenses hybrides","focus":"Collectif","intro":"Étudier la zone comme une suite de rotations et non une forme statique.","observe":["Distances X2-X3-X4","Pistoning et retour dans le gap","M vers press / press vers M","Adaptation gauchère-droitière"],"questions":["Qui sort, qui couvre, qui protège 6 ?","Quel tir la défense choisit-elle de concéder ?"]},
 {"title":"Attaquer la zone","focus":"Contre-mesures","intro":"Voir comment une attaque déplace la zone avant de l'ouvrir.","observe":["Wing-across et surcharge","Drive 2/4","Double post","Fixation puis transfert opposé"],"questions":["Quelle défenseure doit être déplacée en premier ?","L'attaque exploite-t-elle l'espace ou le crée-t-elle ?"]},
 {"title":"Sprint & contre-attaque","focus":"Transition +","intro":"Commencer l'analyse avant même le changement officiel de possession.","observe":["Anticipation du tir/turnover","Trois premiers mouvements du sprint","Largeur des couloirs","2v1 et 3v2 : fixation avant passe"],"questions":["Qui part la première et pourquoi ?","La porteuse force-t-elle une défenseure à choisir ?"]},
 {"title":"Repli défensif","focus":"Transition −","intro":"Protéger le danger avant de chercher à retrouver son adversaire initial.","observe":["Safety et protection de l'axe","Switch en course","Pression sur première passe","Reconstruction des match-ups"],"questions":["Qui doit abandonner son match-up ?","Comment transformer 3v2 en 3v3 ?"]},
 {"title":"6v5 / 5v6","focus":"Spécial teams","intro":"Décomposer les rotations, le shot block et la manipulation de la gardienne.","observe":["4-2 vers 3-3 dynamique","Post pop / cross-post","Near-side vs cross-cage block","Retour de l'exclue"],"questions":["Quelle rotation est déclenchée par le fake ?","Où est le one-more ?"]},
 {"title":"Tir & gardienne","focus":"Finir","intro":"Relier préparation du tir, bloc défensif et position de la gardienne.","observe":["Hauteur de jambes et équilibre","Fake court vs fake long","Tir derrière le bloc","Manipulation du premier poteau"],"questions":["Quelle partie du but est réellement disponible ?","Le tir est-il créé avant l'armé ?"]},
 {"title":"Intelligence de match","focus":"Décision","intro":"Analyser le choix en fonction du score, du chrono, du risque et de la possession suivante.","observe":["Fin de possession","No-foul / foul tactique","Ralentir une contre-attaque","Choix du système après temps mort"],"questions":["Le meilleur geste est-il aussi la meilleure décision de match ?","Quel risque est acceptable ici ?"]},
]

TAGS = ["hip advantage","inside water","seal","re-seal","second contact","slow-fast","create the catch","eye manipulation","key pass","skip","one-more","front","3/4 centre","M-zone","piston","switch","shot block","sprint start","lane width","2v1 fix","3v2 fix","safety","recovery","goalkeeper outlet","lefty adjustment","clock management"]

@router.get("/analysis/video-session-elite")
def video_session_elite(request: Request):
    return templates.TemplateResponse(request, "video_session_elite.html", {"app_name":"AquaMetric","request":request,"user":request.session.get("user_id"),"web_demo_mode":False,"chapters":CHAPTERS,"tags":TAGS})
