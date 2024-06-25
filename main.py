import AngelIntegration
from datetime import datetime, timedelta
import time
import traceback
import pandas as pd

def get_user_settings():
    global result_dict
    # Symbol,lotsize,Stoploss,Target1,Target2,Target3,Target4,Target1Lotsize,Target2Lotsize,Target3Lotsize,Target4Lotsize,BreakEven,ReEntry
    try:
        csv_path = 'TradeSettings.csv'
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        result_dict = {}
        # Symbol,EMA1,EMA2,EMA3,EMA4,lotsize,Stoploss,Target,Tsl
        for index, row in df.iterrows():
            # Create a nested dictionary for each symbol
            symbol_dict = {
                'Symbol': row['Symbol'],"VIX_CONDITION":None,"BaseSymbol":row['BaseSymbol'],"StepNumber":row['StepNumber'],
                "StepDistance":row['StepDistance'],'TradeExpiery':row['TradeExpiery'],"runonce":False,"SelectedPremium":row['SelectedPremium'],"CE_CONTRACT":None,"PE_Contract":None
            }
            result_dict[row['Symbol']] = symbol_dict
        print("result_dict: ", result_dict)
    except Exception as e:
        print("Error happened in fetching symbol", str(e))

def write_to_order_logs(message):
    with open('OrderLog.txt', 'a') as file:  # Open the file in append mode
        file.write(message + '\n')

def delete_file_contents(file_name):
    try:
        # Open the file in write mode, which truncates it (deletes contents)
        with open(file_name, 'w') as file:
            file.truncate(0)
        print(f"Contents of {file_name} have been deleted.")
    except FileNotFoundError:
        print(f"File {file_name} not found.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

result_dict={}


def custom_round(price, symbol):
    rounded_price = None
    if symbol == "NIFTY":
        last_two_digits = price % 100
        if last_two_digits < 25:
            rounded_price = (price // 100) * 100
        elif last_two_digits < 75:
            rounded_price = (price // 100) * 100 + 50
        else:
            rounded_price = (price // 100 + 1) * 100
            return rounded_price

    elif symbol == "BANKNIFTY":
        last_two_digits = price % 100
        if last_two_digits < 50:
            rounded_price = (price // 100) * 100
        else:
            rounded_price = (price // 100 + 1) * 100
        return rounded_price

    else:
        pass

    return rounded_price

def get_api_credentials():
    credentials = {}
    delete_file_contents("OrderLog.txt")
    try:
        df = pd.read_csv('Credentials.csv')
        for index, row in df.iterrows():
            title = row['Title']
            value = row['Value']
            credentials[title] = value
    except pd.errors.EmptyDataError:
        print("The CSV file is empty or has no data.")
    except FileNotFoundError:
        print("The CSV file was not found.")
    except Exception as e:
        print("An error occurred while reading the CSV file:", str(e))

    return credentials
get_user_settings()
credentials_dict = get_api_credentials()
api_key=credentials_dict.get('apikey')
username=credentials_dict.get('USERNAME')
pwd=credentials_dict.get('pin')
totp_string=credentials_dict.get('totp_string')
AngelIntegration.login(api_key=api_key,username=username,pwd=pwd,totp_string=totp_string)
AngelIntegration.symbolmpping()
# 2941,99926017,India VIX,INDIA VIX,,0.0,1,AMXIDX,NSE,0.000000
strikeListCe= {}
strikeListPe= {}

def genertaepricedictpe(price, step, distance,BaseSymbol,formatted_date):
    start_price = price - (step * distance)
    end_price = price
    price_list = [start_price + i * distance for i in range((end_price - start_price) // distance + 1)]
    price_dict = {price: {"PESymbol": f"{BaseSymbol}{formatted_date}{price}PE", "PEPREMIUM": "PRE"} for price in
                  price_list}
    for price in price_dict:
        pe_symbol = price_dict[price]["PESymbol"]
        params = {'Symbol': BaseSymbol,  'PESymbol': pe_symbol}
        price_dict[price]["PEPREMIUM"] = AngelIntegration.get_ltp(segment="NFO", symbol=params['PESymbol'],
                                                                  token=get_token(params['PESymbol']))

    return price_dict


def generatepricedictce(price, step, distance,BaseSymbol,formatted_date):
    start_price = price
    end_price = price + (step * distance)
    price_list = [start_price + i * distance for i in range((end_price - start_price) // distance + 1)]
    price_dict = {price: {"CESymbol": f"{BaseSymbol}{formatted_date}{price}CE", "CEPREMIUM": "PRE"} for price in price_list}
    for price in price_dict:
        ce_symbol = price_dict[price]["CESymbol"]
        params = {'Symbol': BaseSymbol, 'CESymbol': ce_symbol}
        price_dict[price]["CEPREMIUM"] = AngelIntegration.get_ltp(segment="NFO", symbol=params['CESymbol'],
                                                                  token=get_token(params['CESymbol']))
    return price_dict

def finc_closest_Pe(price_dict, target_premium):
    closest_pe_symbol = None
    closest_pe_premium = float('-inf')
    for price in price_dict:
        pe_premium = price_dict[price]["PEPREMIUM"]
        if pe_premium < target_premium and pe_premium > closest_pe_premium:
            closest_pe_premium = pe_premium
            closest_pe_symbol = price_dict[price]["PESymbol"]

    return  closest_pe_symbol

def finc_closest_Ce(price_dict, target_premium):
    closest_ce_symbol = None
    closest_ce_premium = float('-inf')
    for price in price_dict:
        ce_premium = price_dict[price]["CEPREMIUM"]
        if ce_premium < target_premium and ce_premium > closest_ce_premium:
            closest_ce_premium = ce_premium
            closest_ce_symbol = price_dict[price]["CESymbol"]

    return closest_ce_symbol

def find_closest_symbols(price_dict, target_premium):
    closest_ce_symbol = None
    closest_pe_symbol = None
    closest_ce_premium = float('-inf')
    closest_pe_premium = float('-inf')

    for price in price_dict:
        ce_premium = price_dict[price]["CEPREMIUM"]
        pe_premium = price_dict[price]["PEPREMIUM"]

        if ce_premium < target_premium and ce_premium > closest_ce_premium:
            closest_ce_premium = ce_premium
            closest_ce_symbol = price_dict[price]["CESymbol"]

        if pe_premium < target_premium and pe_premium > closest_pe_premium:
            closest_pe_premium = pe_premium
            closest_pe_symbol = price_dict[price]["PESymbol"]

    return closest_ce_symbol, closest_pe_symbol

def get_token(symbol):
    df= pd.read_csv("Instrument.csv")
    row = df.loc[df['symbol'] == symbol]
    if not row.empty:
        token = row.iloc[0]['token']
        return token
def main_strategy():
    global result_dict,strikeListCe,strikeListPe
    try:
        for symbol, params in result_dict.items():
            symbol_value = params['Symbol']
            timestamp = datetime.now()
            timestamp = timestamp.strftime("%d/%m/%Y %H:%M:%S")
            if isinstance(symbol_value, str):
                if params['runonce']==False:
                    params['runonce'] = True
                    VixCurrentltp = AngelIntegration.get_ltp(segment="NSE", symbol="INDIA VIX", token=99926017)
                    if VixCurrentltp<18:
                        params["VIX_CONDITION"]=True
                    if params["VIX_CONDITION"] == True:
                        SpotLtp=int(custom_round(price=AngelIntegration.get_ltp(segment="NFO", symbol=params['Symbol'],
                                                                      token=get_token(params['Symbol'])),symbol=params['BaseSymbol']))
                        date_obj = datetime.strptime(params["TradeExpiery"], "%d-%b-%y")
                        formatted_date = date_obj.strftime("%d%b%y").upper()


                        # strikeList=generate_price_dict(price=SpotLtp, step=params["StepNumber"], distance=params["StepDistance"]
                        #                                ,BaseSymbol=params['BaseSymbol'],formatted_date=formatted_date)

                        strikeListCe=generatepricedictce(price=SpotLtp, step=params["StepNumber"], distance=params["StepDistance"]
                                                       ,BaseSymbol=params['BaseSymbol'],formatted_date=formatted_date)
                        strikeListPe=genertaepricedictpe(price=SpotLtp, step=params["StepNumber"], distance=params["StepDistance"]
                                                       ,BaseSymbol=params['BaseSymbol'],formatted_date=formatted_date)
                        print("strikeListCe: ", strikeListCe)
                        print("strikeListPe: ", strikeListPe)
                        params["PE_Contract"]=finc_closest_Pe(strikeListPe, target_premium=params['SelectedPremium'])
                        params["CE_CONTRACT"] = finc_closest_Ce(strikeListCe, target_premium=params['SelectedPremium'])

                        if (
                                params["CE_CONTRACT"] is not None or
                                params["PE_Contract"] is not None
                        ):
                            OrderLog = f"{timestamp} CE_CONTRACT:  {params['CE_CONTRACT']}, PE_Contract: {params['PE_Contract']} @ {params['Symbol']} "
                            print(OrderLog)
                            write_to_order_logs(OrderLog)
                        if (
                                params["CE_CONTRACT"]is  None or
                                params["PE_Contract"]is  None
                        ):
                            OrderLog=f"{timestamp} Either CE_CONTRACT or PE_Contract is none no trading will be done in @ {params['Symbol']} "
                            print(OrderLog)
                            write_to_order_logs(OrderLog)

                if params["VIX_CONDITION"] == True and params["CE_CONTRACT"]is not None and params["PE_Contract"]is not None :
                    pass



    except Exception as e:
        print("Error happened in Main strategy loop: ", str(e))
        traceback.print_exc()

while True:
    StartTime = credentials_dict.get('starttime')
    Stoptime = credentials_dict.get('stoptime')
    start_time = datetime.strptime(StartTime, '%H:%M').time()
    stop_time = datetime.strptime(Stoptime, '%H:%M').time()

    current_time = datetime.now().time()
    main_strategy()
    time.sleep(1)

    if current_time>=start_time and current_time< stop_time:
        main_strategy()
        time.sleep(1)
