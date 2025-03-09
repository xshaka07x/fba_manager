from app.utils.fetch_keepa import get_keepa_data

def test_keepa_price():
    # Test avec le sirop d'abricot Teisseire
    ean = "3092718637279"
    prix_retail = 2.55  # Prix Stokomani
    
    print(f"🔍 Test Keepa pour EAN: {ean}")
    print(f"💰 Prix retail: {prix_retail}€")
    
    prix_amazon, roi, profit, sales_estimation, status = get_keepa_data(ean, prix_retail)
    
    if status == "OK":
        print(f"✅ Test réussi!")
        print(f"   - Prix Amazon: {prix_amazon}€")
        print(f"   - ROI: {roi}%")
        print(f"   - Profit: {profit}€")
    else:
        print(f"❌ Test échoué: {status}")

if __name__ == "__main__":
    test_keepa_price() 