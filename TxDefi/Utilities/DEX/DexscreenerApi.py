from TxDefi.Data.MarketDTOs import ExtendedMetadata
import HttpUtils

def get_metadata(token_address: str)->ExtendedMetadata:
    pair_id = token_address
    uri_request = f"https://api.dexscreener.com/latest/dex/tokens/{pair_id}"
    response = HttpUtils.get_request(uri_request)

    if response and response.get('pairs'):
        if len(response['pairs']) > 0:
            info = response['pairs'][0].get('info')

            if info:
                ret_info = ExtendedMetadata(token_address)
                ret_info.image_uri = info['imageUrl']
                ret_info.banner_url = info['header']
                ret_info.open_graph_url = info['openGraph']  

                for social in info.get('socials', {}):
                    ret_info.socials.update(social.get('type', ''), social.get('url',))
              
                websites = info.get('websites')

                if websites and len(websites) > 0:
                    url = websites[0].get('url')
                    ret_info.socials.update('website', url) #TODO could be more sites
                
                return ret_info
