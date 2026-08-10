import asyncio
import unittest

from quality_diagnosis.job_manager import AsyncJobManager


class JobManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_job_progress_and_completion(self):
        manager = AsyncJobManager()

        async def runner(update):
            update(50, "중간")
            await asyncio.sleep(0)
            return {"ok": True}

        created = await manager.create("test", "테스트", runner)
        for _ in range(20):
            job = await manager.get(created["job_id"])
            if job["status"] == "completed":
                break
            await asyncio.sleep(0.01)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["progress"], 100)
        self.assertTrue(job["result"]["ok"])

    async def test_running_job_can_be_cancelled(self):
        manager = AsyncJobManager()

        async def runner(update):
            update(10, "대기")
            await asyncio.Event().wait()
            return {}

        created = await manager.create("slow", "느린 작업", runner)
        await asyncio.sleep(0)
        await manager.cancel(created["job_id"])
        for _ in range(20):
            job = await manager.get(created["job_id"])
            if job["status"] == "cancelled":
                break
            await asyncio.sleep(0.01)
        self.assertEqual(job["status"], "cancelled")
        self.assertTrue(job["cancel_requested"])


if __name__ == "__main__":
    unittest.main()
