import aiohttp

class ProxyService:
    BASE_URL = "https://mtdproxy.com/api"
    
    @staticmethod
    async def buy_proxy(api_key: str, proxy_type: str = "Viettel", count: int = 1):
        """
        Buy proxy: /muaproxy.php?key=...&loaiproxy=...&soluong=...
        """
        url = f"{ProxyService.BASE_URL}/muaproxy.php"
        params = {"key": api_key, "loaiproxy": proxy_type, "soluong": count}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                # Image shows: {"status": 100, "data": [...]}
                return data

    @staticmethod
    async def get_proxy_list(api_key: str):
        """
        Get list: /apidolbaomat.php?key=...
        """
        url = f"{ProxyService.BASE_URL}/apidolbaomat.php"
        params = {"key": api_key}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json() 
                # Should return list of proxies
                return data

    @staticmethod
    async def exchange_ip(api_key: str, proxy_id: str):
        """
        For rotating IP: /doiproxy.php?key=...&idproxy=...
        """
        url = f"{ProxyService.BASE_URL}/doiproxy.php"
        params = {"key": api_key, "idproxy": proxy_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                return await resp.json()
                
    @staticmethod
    async def auth_to_noauth(api_key: str, proxy_id: str, current_ip: str):
        """
        Switch auth mode usually involves setting 'ip' for authorization
        Endpoint hypothetical: /update_ip.php?key=...&id=...&ip=...
        User requested "auth to no auth", meaning IP-Whitelist authentication.
        Usually mtdproxy allows setting whitelisted IP.
        """
        # Placeholder based on common proxy API patterns
        pass
