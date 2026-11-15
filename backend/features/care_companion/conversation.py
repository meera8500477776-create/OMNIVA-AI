import asyncio, time, uuid
from .contracts import CallState, PersonaId, VoiceSession
from .personas import PERSONAS
from .demo_provider import DemoCompanion
from .voice_adapter import VoiceProviderSet
class Conversation:
 def __init__(self, *, demo=True, providers=None, timeout=5): self.demo,self.providers,self.timeout=demo,providers or VoiceProviderSet(),timeout; self.sessions={}; self.transcripts={}
 async def start(self, persona: PersonaId, locale="en") -> VoiceSession:
  if locale.split("-")[0].casefold() not in {"en","te"}: raise ValueError("Supported demo locales are en and te")
  if not self.demo: self.providers.require()
  sid=str(uuid.uuid4()); s=VoiceSession(sid,persona,locale,self.demo,"active"); self.sessions[sid]=s; self.transcripts[sid]=[]; return s
 async def reply(self, sid, text):
  s=self.sessions[sid]
  if s.state != "active": raise ValueError("Session is not active")
  if self.demo: answer=DemoCompanion().reply(s.persona,text,s.locale)
  else: answer=await asyncio.wait_for(self.providers.llm.respond([{"role":"user","content":text}],PERSONAS[s.persona].style,s.locale),self.timeout)
  self.transcripts[sid].extend([{"role":"user","text":text},{"role":"assistant","text":answer}]); return answer
 def switch(self,sid,persona): self.sessions[sid]=VoiceSession(sid,persona,self.sessions[sid].locale,self.demo,self.sessions[sid].state)
