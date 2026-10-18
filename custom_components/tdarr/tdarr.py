import logging
import requests

_LOGGER = logging.getLogger(__name__)

class Server(object):
    # Class representing a tdarr server
    def __init__(self, url, port, apikey=""):
        self.url = url
        self.baseurl = 'http://' + self.url + ':' + port + '/api/v2/'
        self.headers = {
            'Content-Type': 'application/json',
            'x-api-key': apikey
        }
        
    def getNodes(self):
        r = requests.get(self.baseurl + 'get-nodes', headers=self.headers, timeout=30)
        if r.status_code == 200:
            result = r.json()
            return result
        else:
            r.raise_for_status()

    def getStatus(self):
        r = requests.get(self.baseurl + 'status', headers=self.headers, timeout=30)
        if r.status_code == 200:
            result = r.json()
            return result
        else:
            r.raise_for_status()
    
    def getLibraries(self):
        libraries = []
        library = self.getPies()
        library["name"] = "All"
        libraries.append(library)
        for lib in self.getLibraryStats():
            library2 = self.getPies(lib["_id"])
            library2["name"] = lib["name"]
            library2["_id"] = lib["_id"]
            library2["folder"] = lib.get("folder", "")
            library2["processLibrary"] = lib.get("processLibrary")
            libraries.append(library2)


        return libraries

    def getStats(self):
        post = {
            "data": {
                "collection":"StatisticsJSONDB",
                "mode":"getById",
                "docID":"statistics",
                "obj":{}
                },
            "timeout":1000
        }
        r = requests.post(self.baseurl + 'cruddb', json = post, headers=self.headers, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            r.raise_for_status()
    
    def getLibraryStats(self):
        post = {
            "data": {
                "collection":"LibrarySettingsJSONDB",
                "mode":"getAll",
                },
            "timeout":20000
        }
        r = requests.post(self.baseurl + 'cruddb', json = post, headers=self.headers, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            r.raise_for_status()
    def getPies(self, libraryID=""):
        post = {
            "data": {
                "libraryId":libraryID
                },
        }
        r = requests.post(self.baseurl + 'stats/get-pies', json = post, headers=self.headers, timeout=30)
        if r.status_code == 200:
            return r.json()["pieStats"]
        else:
            r.raise_for_status()
        
    def getStaged(self):
        post = {
            "data": {
                "filters":[],
                "start":0,
                "pageSize":10,
                "sorts":[],
                "opts":{}
                },
            "timeout":1000
        }
        r = requests.post(self.baseurl + 'client/staged', json = post, headers=self.headers, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            r.raise_for_status()
        
    def getSettings(self):  
        post = {
            "data": {
                "collection":"SettingsGlobalJSONDB",
                "mode":"getById",
                "docID":"globalsettings",
                "obj":{}
                },
            "timeout":1000
        }
        r = requests.post(self.baseurl + 'cruddb', json = post, headers=self.headers, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            return {"message": r.text, "status_code": r.status_code, "status": "ERROR"}
        
    def pauseNode(self, nodeID, status):

        if nodeID == "pauseAll":
            data = {
                "data":{
                    "collection":"SettingsGlobalJSONDB",
                    "mode":"update",
                    "docID":"globalsettings",
                    "obj":{
                        "pauseAllNodes": status
                        }
                    },
                    "timeout":20000
                }
            r = requests.post(self.baseurl + 'cruddb', json=data, headers=self.headers, timeout=30)
        elif nodeID == "ignoreSchedules":
            data = {
                "data":{
                    "collection":"SettingsGlobalJSONDB",
                    "mode":"update",
                    "docID":"globalsettings",
                    "obj":{
                        "ignoreSchedules": status
                        }
                    },
                    "timeout":20000
                }
            r = requests.post(self.baseurl + 'cruddb', json=data, headers=self.headers, timeout=30)
        else:
            data = {
                "data": {
                    "nodeID": nodeID,
                    "nodeUpdates": {
                        "nodePaused": status
                    }
                }
            }
            r = requests.post(self.baseurl + 'update-node', json=data, headers=self.headers, timeout=30)
        if r.status_code == 200:
            return "OK"
        else:
            r.raise_for_status()

    def setProcessLibrary(self, library_id, enabled):
        """Update only the processing flag of the selected library."""
        if not library_id or not isinstance(enabled, bool):
            raise ValueError("Library ID and boolean state are required")
        response = requests.post(
            self.baseurl + "cruddb",
            json={"data": {
                "collection": "LibrarySettingsJSONDB",
                "mode": "update",
                "docID": library_id,
                "obj": {"processLibrary": enabled},
            }, "timeout": 20000},
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()

    def scanLibrary(self, library_id, folderpath):
        """Find new files in one library using its exact ID and source folder."""
        if not library_id or not isinstance(folderpath, str) or not folderpath.strip():
            raise ValueError("Library ID and source folder are required")
        data = {
            "data": {
                "scanConfig": {
                    "dbID": library_id,
                    "arrayOrPath": folderpath,
                    "mode": "scanFindNew",
                }
            }
        }
        response = requests.post(
            self.baseurl + "scan-files", json=data, headers=self.headers, timeout=30
        )
        response.raise_for_status()
        # Tdarr returns plain text here; do not attempt JSON decoding.

    def refreshLibrary(self, libraryname, mode, folderpath):
        stats = self.getLibraryStats()
        libid = None
        _LOGGER.debug(mode)

        if mode == "":
            mode = "scanFindNew"
        matches = [lib for lib in stats if libraryname in (lib["name"], lib["_id"])]
        if len(matches) != 1:
            return {"ERROR": "Library name or ID must match exactly one library"}
        libid = matches[0]["_id"]

        if libid is None:
            return {"ERROR": "Library Name not found"}


        data = {
            "data": {
                "scanConfig": {
                    "dbID" : libid,
                    "arrayOrPath": folderpath,
                    "mode": mode
                }
            }
        }

        r = requests.post(self.baseurl + "scan-files", json=data, headers=self.headers, timeout=30)

        if r.status_code == 200:
            _LOGGER.debug(r.text)
            return {"SUCCESS"}
        else:
            return {"ERROR": r.text}



            
    


    

    