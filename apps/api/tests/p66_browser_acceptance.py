from sqlalchemy import select,func
from pao.db import Session
from pao.models import ArtifactLearningProposal,ArtifactLearningAudit,BrainNote
from test_artifact_learning import fixture
from test_brain_manager import brains_on
from p6_browser_harness import browser

async def test_artifact_learning_browser(client,identity,brains_on,monkeypatch):
    brain,file,text=await fixture(client,identity,monkeypatch)
    await browser('scripts/verify_artifact_browser.cjs','PAO_ARTIFACT_BROWSER_FIXTURE',{'brain':brain['id'],'file':file['id'],'quote':'Thị trường Việt Nam.'},'artifact')
    async with Session() as db:
        assert await db.scalar(select(func.count(ArtifactLearningProposal.id)))==2
        assert await db.scalar(select(func.count(ArtifactLearningAudit.id)))==5
        assert await db.scalar(select(func.count(BrainNote.id)).where(BrainNote.trashed_at.is_(None)))==1
