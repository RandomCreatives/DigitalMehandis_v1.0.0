import asyncio
import asyncpg

async def check():
    try:
        conn = await asyncpg.connect('postgresql://ethioqs:ethioqs_secret@localhost:5432/ethioqs')
        print('Postgres reachable')
        await conn.close()
    except Exception as e:
        print(f'Postgres NOT reachable: {e}')

if __name__ == "__main__":
    asyncio.run(check())
