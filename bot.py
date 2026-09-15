import os, asyncio, aiohttp
from dataclasses import dataclass
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application,CommandHandler,ContextTypes
load_dotenv()
TOKEN=os.getenv("TELEGRAM_BOT_TOKEN",""); OWNER=int(os.getenv("TELEGRAM_USER_ID","0")); cash=float(os.getenv("STARTING_BALANCE_USD","100"))
running=False; positions={}; seen=set()
MIN_MC,MAX_MC,MIN_LIQ=5000,50000,3000
@dataclass
class Pos: address:str; symbol:str; entry:float; size:float; peak:float
async def js(s,u):
 try:
  async with s.get(u,timeout=10) as r:return await r.json() if r.status==200 else None
 except:return None
async def pair(s,a):
 d=await js(s,f"https://api.dexscreener.com/latest/dex/tokens/{a}"); ps=(d or {}).get("pairs") or []
 ps=[p for p in ps if p.get("chainId")=="solana"]
 return max(ps,key=lambda p:float((p.get("liquidity") or {}).get("usd") or 0)) if ps else None
def met(p):
 return (float(p.get("marketCap") or p.get("fdv") or 0),float((p.get("liquidity") or {}).get("usd") or 0),float(p.get("priceUsd") or 0),(p.get("txns") or {}).get("m5") or {},float((p.get("volume") or {}).get("m5") or 0),float((p.get("priceChange") or {}).get("m5") or 0))
def good(p):
 mc,lq,pr,tx,v,ch=met(p); b=int(tx.get("buys") or 0); s=int(tx.get("sells") or 0)
 return MIN_MC<=mc<=MAX_MC and lq>=MIN_LIQ and pr>0 and b+s>=6 and b>s and v>=250 and -10<ch<40
async def scan(app):
 global cash
 async with aiohttp.ClientSession() as s:
  d=await js(s,"https://api.dexscreener.com/token-profiles/latest/v1")
  for x in (d or [])[:60]:
   if not running or len(positions)>=3: break
   if x.get("chainId")!="solana":continue
   a=x.get("tokenAddress")
   if not a or a in seen:continue
   p=await pair(s,a)
   if p and good(p) and cash>=5:
    mc,lq,pr,*_=met(p); sym=p.get("baseToken",{}).get("symbol","?")
    positions[a]=Pos(a,sym,pr,5,pr); cash-=5; seen.add(a)
    if OWNER: await app.bot.send_message(OWNER,f"🟢 PAPER BUY {sym}\n$5 | MC ${mc:,.0f} | Liq ${lq:,.0f}")
async def manage(app):
 global cash
 async with aiohttp.ClientSession() as s:
  for a,pos in list(positions.items()):
   p=await pair(s,a)
   if not p:continue
   mc,lq,pr,*_=met(p); pos.peak=max(pos.peak,pr); ret=pr/pos.entry-1; draw=pr/pos.peak-1
   if ret<=-.20 or (pos.peak/pos.entry-1>=.30 and draw<=-.18):
    value=pos.size*(pr/pos.entry); cash+=value; del positions[a]
    if OWNER: await app.bot.send_message(OWNER,f"🔴 PAPER SELL {pos.symbol}\nReturn {ret:+.1%} | value ${value:.2f}")
async def loop(app):
 while True:
  try: await manage(app); await scan(app)
  except Exception as e: print(e)
  await asyncio.sleep(60)
def ok(u):return OWNER==0 or u.effective_user.id==OWNER
async def start(u,c):
 if ok(u):await u.message.reply_text("🤖 Solana Microcap AutoTrader — PAPER MODE\n/run /pause /status /positions /scan")
async def run(u,c):
 global running
 if ok(u):running=True;await u.message.reply_text("▶️ Auto-Trading gestartet (Paper).")
async def pause(u,c):
 global running
 if ok(u):running=False;await u.message.reply_text("⏸ Neue Käufe pausiert.")
async def status(u,c):
 if ok(u):await u.message.reply_text(f"{'▶️ RUNNING' if running else '⏸ PAUSED'}\nCash ${cash:.2f}\nPositionen {len(positions)}/3\nMC Filter $5K-$50K")
async def poss(u,c):
 if ok(u):await u.message.reply_text("\n".join(f"{p.symbol}: ${p.size:.2f}" for p in positions.values()) or "Keine Positionen.")
async def once(u,c):
 if ok(u):await u.message.reply_text("🔎 Scan…");await scan(c.application);await u.message.reply_text("Fertig.")
async def init(app):asyncio.create_task(loop(app))
def main():
 if not TOKEN:raise SystemExit("TELEGRAM_BOT_TOKEN fehlt in .env")
 app=Application.builder().token(TOKEN).post_init(init).build()
 for n,f in [("start",start),("run",run),("pause",pause),("status",status),("positions",poss),("scan",once)]:app.add_handler(CommandHandler(n,f))
 app.run_polling()
if __name__=="__main__":main()
