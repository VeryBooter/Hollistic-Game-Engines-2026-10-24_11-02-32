using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AirIntercept {
    [InitializeOnLoad] public static class AirDemoEditor {
        const string ScenePath="Assets/AirInterceptDemo/AirInterceptDemo.unity";
        const string StateKey="AirIntercept.Verification";
        static string Root {get{var root=Environment.GetEnvironmentVariable("PHYSICS_ROOT");return string.IsNullOrEmpty(root)?Path.GetFullPath(Path.Combine(Application.dataPath,"../Physics/artifacts")):Path.Combine(root,"artifacts");}}
        static string Request {get{return Path.Combine(Root,"air-demo-verify.request");}}
        static AirDemoEditor(){EditorApplication.update+=Poll;}

        [MenuItem("Tools/Air Intercept/Open Demo")]
        public static void Open(){
            if(!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())return;
            EditorSceneManager.OpenScene(ScenePath);
        }
        [MenuItem("Tools/Air Intercept/Verify Demo")]
        public static void Verify(){Directory.CreateDirectory(Root);File.WriteAllText(Request,"verify");}
        public static void BatchVerify(){Verify();}

        static void Finish(string message){
            File.WriteAllText(Path.Combine(Root,"air-demo-unity-result.json"),message);
            SessionState.SetString(StateKey,"");
            if(File.Exists(Request))File.Delete(Request);
            if(Application.isBatchMode){EditorApplication.Exit(message.Contains("\"ok\":true")?0:1);return;}
            if(EditorApplication.isPlaying)EditorApplication.isPlaying=false;
        }
        static void Poll(){
            if(EditorApplication.isCompiling||EditorApplication.isUpdating)return;
            string state=SessionState.GetString(StateKey,"");
            if(state=="" && File.Exists(Request)){
                if(EditorApplication.isPlaying){Finish("{\"ok\":false,\"error\":\"Stop Play Mode before verification\"}");return;}
                if(SceneManager.GetActiveScene().isDirty){Finish("{\"ok\":false,\"error\":\"Save the current scene before verification\"}");return;}
                SessionState.SetString(StateKey,"running");
                SessionState.SetBool(StateKey+"Bands",false);
                SessionState.SetFloat(StateKey+"Start",(float)EditorApplication.timeSinceStartup);
                EditorSceneManager.OpenScene(ScenePath);
                EditorApplication.isPlaying=true;
                return;
            }
            if(state=="")return;
            float elapsed=(float)EditorApplication.timeSinceStartup-SessionState.GetFloat(StateKey+"Start",0);
            if(elapsed>75){Finish("{\"ok\":false,\"error\":\"Play Mode verification timed out\"}");return;}
            var demo=AirInterceptDemo.Current;
            if(!EditorApplication.isPlaying||demo==null)return;
            if(demo.Error!=null){Finish(JsonUtility.ToJson(new Result {ok=false,error=demo.Error}));return;}
            if(demo.Latest==null)return;
            if(state=="running" && demo.Latest.time_s>1){
                if(!SelectBand("1e9 Hz")){Finish("{\"ok\":false,\"error\":\"Missing radar band control\"}");return;}
                SessionState.SetString(StateKey,"low-band");return;
            }
            if(state=="low-band" && Math.Abs(demo.Latest.player_sensor.frequency_Hz-1e9)<1e5){
                SelectBand("9.4e10 Hz");SessionState.SetString(StateKey,"high-band");return;
            }
            if(state=="high-band" && Math.Abs(demo.Latest.player_sensor.frequency_Hz-94e9)<1e6){
                SelectBand("1e10 Hz");SessionState.SetString(StateKey,"nominal-band");return;
            }
            if(state=="nominal-band" && Math.Abs(demo.Latest.player_sensor.frequency_Hz-1e10)<1e5 && demo.Latest.time_s>3){
                SessionState.SetBool(StateKey+"Bands",true);
                if(Application.isBatchMode)CapturePreview();
                else ScreenCapture.CaptureScreenshot(Path.Combine(Root,"air-demo.png"));
                SessionState.SetString(StateKey,"screenshot");SessionState.SetFloat(StateKey+"Shot",(float)EditorApplication.timeSinceStartup);
            }else if(state=="screenshot" && (float)EditorApplication.timeSinceStartup-SessionState.GetFloat(StateKey+"Shot",0)>2){
                var frame=demo.Latest;
                bool captured=File.Exists(Path.Combine(Root,"air-demo.png"));
                Finish(JsonUtility.ToJson(new Result{ok=true,time_s=frame.time_s,player_detected=frame.player_sensor.detected,opponent_detected=frame.opponent_sensor.detected,screenshot=captured?"Physics/artifacts/air-demo.png":"",screenshot_has_hud=captured,frequency_controls_verified=SessionState.GetBool(StateKey+"Bands",false)}));
            }
        }
        static bool SelectBand(string name){
            foreach(var button in UnityEngine.Object.FindObjectsByType<UnityEngine.UI.Button>(FindObjectsSortMode.None))
                if(button.name==name){button.onClick.Invoke();return true;}
            return false;
        }
        static void CapturePreview(){
            // The camera-space Canvas also renders into the verification image.
            var camera=AirInterceptDemo.Current.FlightCamera;
            if(camera==null)return;
            var target=new RenderTexture(1280,720,24);
            var previous=RenderTexture.active;
            var previousTarget=camera.targetTexture;
            var image=new Texture2D(1280,720,TextureFormat.RGB24,false);
            try{
                camera.targetTexture=target;Canvas.ForceUpdateCanvases();camera.Render();RenderTexture.active=target;
                image.ReadPixels(new Rect(0,0,1280,720),0,0);image.Apply();
                File.WriteAllBytes(Path.Combine(Root,"air-demo.png"),image.EncodeToPNG());
            }finally{camera.targetTexture=previousTarget;RenderTexture.active=previous;target.Release();UnityEngine.Object.DestroyImmediate(target);UnityEngine.Object.DestroyImmediate(image);}
        }
        [Serializable] sealed class Result {public bool ok,player_detected,opponent_detected,screenshot_has_hud,frequency_controls_verified;public float time_s;public string error,screenshot;}
    }
}
