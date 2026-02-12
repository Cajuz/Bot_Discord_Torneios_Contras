import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def test():
    uri = os.getenv("MONGO_URI")
    
    if not uri:
        print("❌ MONGO_URI não encontrado")
        return
    
    print("🔄 Conectando ao MongoDB...")
    print(f"📡 Cluster: x1-bot-cluster.p1wq1wh.mongodb.net")
    
    try:
        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=10000)
        
        # Testa ping
        await client.admin.command("ping")
        print("✅ PING bem-sucedido!")
        
        # Lista bancos
        dbs = await client.list_database_names()
        print(f"📂 Bancos disponíveis: {dbs}")
        
        # Testa inserção
        db = client.x1_bot
        test_collection = db.test
        
        result = await test_collection.insert_one({"test": "ok"})
        print(f"📝 Teste de escrita OK (ID: {result.inserted_id})")
        
        # Limpa teste
        await test_collection.delete_one({"test": "ok"})
        print("🧹 Teste limpo")
        
        client.close()
        print("\n🎉 TUDO FUNCIONANDO!")
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        print("\n🔍 Checklist:")
        print("   1. Senha correta no .env?")
        print("   2. Senha tem caracteres especiais? Use URL encode")
        print("   3. IP 0.0.0.0/0 liberado no Network Access?")
        print("   4. Internet funcionando?")

if __name__ == "__main__":
    asyncio.run(test())
