using System;
using System.IO;
using System.Threading;
using System.Diagnostics;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace AirIntercept {
    // Scene visuals and input only. JSBSim is the single authority for both aircraft.
    public sealed class AirInterceptDemo : MonoBehaviour {
        [Serializable] public sealed class Aircraft {
            public float[] position;
            public float yaw, pitch, roll, speed_m_s, throttle;
            public float fuel_kg, initial_fuel_kg, fuel_flow_kg_s, mach;
        }
        [Serializable] public sealed class Sensor {
            public bool detected, illuminated;
            public float range_m, bearing_rad, elevation_rad, radial_velocity_m_s;
            public float frequency_Hz, wavelength_m, beamwidth_rad, transmit_power_W, received_power_W;
            public float noise_power_W, snr_linear, snr_threshold, gain_linear, aperture_m2, rcs_m2;
            public float bandwidth_Hz, range_resolution_m, noise_temperature_K, noise_factor, loss_factor;
            public float ideal_range_m, track_age_s, doppler_Hz, beam_azimuth_rad, beam_elevation_rad, scan_revisit_s;
            public string mode;
            public float[] track_position_m;
        }
        [Serializable] public sealed class Optical {public bool detected;public float wavelength_m,aperture_m,angular_resolution_rad,field_of_view_rad;}
        [Serializable] public sealed class Frame {
            public string type, message;
            public float time_s, range_limit_m, temperature_K, pressure_Pa;
            public Aircraft player, opponent;
            public Sensor player_sensor, opponent_sensor;
            public Optical player_eo, opponent_eo;
            public bool crashed;
        }
        public static AirInterceptDemo Current { get; private set; }
        public Frame Latest { get; private set; }
        public string Error { get; private set; }
        public bool Paused { get; private set; }
        public bool TelemetryFresh {get{return Latest!=null&&(Paused||Time.realtimeSinceStartup-lastReceive<2);}}
        public Camera FlightCamera {get{return view;}}
        public Transform PlayerTransform {get{return blue;}}
        public Transform OpponentTransform {get{return red;}}
        public double FrequencyHz {get;private set;} = 1e10;
        public void SetFrequency(double frequency){FrequencyHz=frequency;}
        public void TogglePause(){Paused=!Paused;}
        Process worker;
        readonly object sync = new object();
        string pending, backendLog = "";
        volatile bool stopping;
        float throttle = .4f, nextSend, lastReceive;
        bool resetRequested, watchOpponent;
        Transform blue, red;
        Camera view;
        Texture2D pixel;
        readonly Color cyan = new Color(.24f,.91f,.96f);
        readonly Color orange = new Color(1,.43f,.25f);

        void Start() {
            Current = this;
            Application.runInBackground = true;
            BuildWorld();
            gameObject.AddComponent<AirSensorHud>();
            StartWorker();
        }
        void StartWorker() {
            try {
                string root = Environment.GetEnvironmentVariable("PHYSICS_ROOT");
                if (string.IsNullOrEmpty(root)) root = Path.GetFullPath(Path.Combine(Application.dataPath,"../Physics"));
                string python = Path.Combine(root,".venv/bin/python");
                if (!File.Exists(python)) throw new FileNotFoundException("Run Physics/scripts/bootstrap.sh first",python);
                worker = new Process { StartInfo = new ProcessStartInfo {
                    FileName=python, Arguments="-u -m physim.air_demo", WorkingDirectory=root,
                    UseShellExecute=false, RedirectStandardInput=true, RedirectStandardOutput=true,
                    RedirectStandardError=true, CreateNoWindow=true
                }};
                worker.Start();
                new Thread(ReadFrames) {IsBackground=true,Name="Flight telemetry"}.Start();
                new Thread(ReadErrors) {IsBackground=true,Name="Flight solver log"}.Start();
            } catch (Exception e) { Error=e.Message; }
        }
        void ReadFrames() {
            try {
                string line;
                while (!stopping && (line=worker.StandardOutput.ReadLine())!=null)
                    lock(sync) pending=line;
            } catch (Exception e) { if (!stopping) lock(sync) backendLog=e.Message; }
        }
        void ReadErrors() {
            try {
                string line;
                while (!stopping && (line=worker.StandardError.ReadLine())!=null)
                    lock(sync) { backendLog += line+"\n"; if (backendLog.Length>6000) backendLog=backendLog.Substring(backendLog.Length-6000); }
            } catch (Exception) { }
        }
        bool Down(string key) {
#if ENABLE_INPUT_SYSTEM
            var k=Keyboard.current;
            if (k==null) return false;
            switch(key) {
                case "w":return k.wKey.isPressed; case "s":return k.sKey.isPressed;
                case "a":return k.aKey.isPressed; case "d":return k.dKey.isPressed;
                case "q":return k.qKey.isPressed; case "e":return k.eKey.isPressed;
                case "shift":return k.leftShiftKey.isPressed||k.rightShiftKey.isPressed;
                case "ctrl":return k.leftCtrlKey.isPressed||k.rightCtrlKey.isPressed;
            }
            return false;
#else
            switch(key) {
                case "shift":return Input.GetKey(KeyCode.LeftShift)||Input.GetKey(KeyCode.RightShift);
                case "ctrl":return Input.GetKey(KeyCode.LeftControl)||Input.GetKey(KeyCode.RightControl);
                default:return Input.GetKey(key);
            }
#endif
        }
        bool Pressed(string key) {
#if ENABLE_INPUT_SYSTEM
            var k=Keyboard.current;
            if(k==null)return false;
            return key=="p"?k.pKey.wasPressedThisFrame:key=="r"?k.rKey.wasPressedThisFrame:k.tabKey.wasPressedThisFrame;
#else
            return key=="tab"?Input.GetKeyDown(KeyCode.Tab):Input.GetKeyDown(key);
#endif
        }
        void Update() {
            if(Pressed("p")) Paused=!Paused;
            if(Pressed("r")) ResetFlight();
            if(Pressed("tab")) watchOpponent=!watchOpponent;
            if(!Paused) throttle=Mathf.Clamp01(throttle+((Down("shift")?1:0)-(Down("ctrl")?1:0))*Time.unscaledDeltaTime*.3f);
            string raw;
            lock(sync) {raw=pending;pending=null;}
            if(raw!=null) {
                try {
                    Frame f=JsonUtility.FromJson<Frame>(raw);
                    if(f.type=="error")Error=f.message;
                    else if(f.player!=null && f.opponent!=null) { Latest=f; lastReceive=Time.realtimeSinceStartup; }
                } catch(Exception e) {Error="Telemetry: "+e.Message;}
            }
            if(worker!=null && !stopping) {
                if(worker.HasExited && Error==null) {lock(sync)Error="Flight worker exited. "+backendLog;}
                if(!worker.HasExited && Time.realtimeSinceStartup>=nextSend) {
                    try {
                        var c=new Control {roll=(Down("d")?1:0)-(Down("a")?1:0),pitch=(Down("w")?1:0)-(Down("s")?1:0),
                            yaw=(Down("e")?1:0)-(Down("q")?1:0),throttle=throttle,paused=Paused,reset=resetRequested,frequency_Hz=FrequencyHz};
                        worker.StandardInput.WriteLine(JsonUtility.ToJson(c)); worker.StandardInput.Flush();resetRequested=false;
                    }catch(Exception e){Error=e.Message;}
                    nextSend=Time.realtimeSinceStartup+1f/30;
                }
            }
            if(Latest==null)return;
            SetPlane(blue,Latest.player);SetPlane(red,Latest.opponent);
            var subject=watchOpponent?red:blue;
            Vector3 wanted=subject.position-subject.forward*28+Vector3.up*10;
            float smooth=1-Mathf.Exp(-Time.unscaledDeltaTime*5);
            view.transform.position=wanted;
            view.transform.rotation=Quaternion.Slerp(view.transform.rotation,Quaternion.LookRotation(subject.position+subject.forward*25-view.transform.position,Vector3.up),smooth);
        }
        [Serializable] sealed class Control {public float roll,pitch,yaw,throttle;public double frequency_Hz;public bool paused,reset;}
        public void ResetFlight(){resetRequested=true;Paused=false;throttle=.4f;}
        static Vector3 Position(Aircraft f){return new Vector3(f.position[0],f.position[1],f.position[2]);}
        static void SetPlane(Transform t,Aircraft f){t.position=Position(f);t.rotation=Quaternion.Euler(-f.pitch*Mathf.Rad2Deg,f.yaw*Mathf.Rad2Deg,-f.roll*Mathf.Rad2Deg);}
        Material Material(Color color) {
            Shader shader=Shader.Find(UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline!=null?"Universal Render Pipeline/Lit":"Standard");
            if(shader==null)shader=Shader.Find("Standard");
            var m=new Material(shader);m.color=color;
            if(m.HasProperty("_Smoothness"))m.SetFloat("_Smoothness",.38f);
            return m;
        }
        GameObject Part(Transform parent,string name,Vector3 position,Vector3 size,Material material,PrimitiveType primitive=PrimitiveType.Cube) {
            var g=GameObject.CreatePrimitive(primitive);g.name=name;g.transform.SetParent(parent,false);
            g.transform.localPosition=position;g.transform.localScale=size;g.GetComponent<Renderer>().sharedMaterial=material;
            Destroy(g.GetComponent<Collider>());return g;
        }
        Transform Plane(string name,Color tint) {
            var root=new GameObject(name).transform;
            var body=Material(new Color(.65f,.72f,.77f));var accent=Material(tint);var dark=Material(new Color(.025f,.08f,.12f));
            Part(root,"Fuselage",Vector3.zero,new Vector3(1.25f,5.5f,1.25f),body,PrimitiveType.Capsule).transform.localRotation=Quaternion.Euler(90,0,0);
            Part(root,"Canopy",new Vector3(0,.65f,2),new Vector3(.85f,.7f,2.7f),dark,PrimitiveType.Sphere);
            // Swept silhouette: procedural mesh, no external model or asset dependency.
            var wing=new GameObject("Swept wings");wing.transform.SetParent(root,false);
            var mesh=new Mesh {vertices=new[]{new Vector3(-.6f,0,2.1f),new Vector3(-6.8f,0,-2.3f),new Vector3(-5.7f,0,-3.2f),new Vector3(-.6f,0,-2),new Vector3(.6f,0,2.1f),new Vector3(6.8f,0,-2.3f),new Vector3(5.7f,0,-3.2f),new Vector3(.6f,0,-2)},
                triangles=new[]{0,2,1,0,3,2,0,1,2,0,2,3,4,5,6,4,6,7,4,6,5,4,7,6}};
            mesh.RecalculateNormals();wing.AddComponent<MeshFilter>().sharedMesh=mesh;wing.AddComponent<MeshRenderer>().sharedMaterial=accent;
            Part(root,"Tailplane",new Vector3(0,.15f,-4),new Vector3(5.2f,.16f,1.5f),accent);
            Part(root,"Fin",new Vector3(0,1.15f,-3.9f),new Vector3(.18f,2.4f,1.9f),accent);
            Part(root,"Engine",new Vector3(0,0,-5.3f),new Vector3(.7f,.7f,.5f),dark,PrimitiveType.Sphere);
            Part(root,"Exhaust",new Vector3(0,0,-5.65f),new Vector3(.46f,.46f,.28f),Material(new Color(1,.49f,.08f)),PrimitiveType.Sphere);
            return root;
        }
        void BuildWorld() {
            foreach(var c in FindObjectsByType<Camera>(FindObjectsSortMode.None))c.enabled=false;
            RenderSettings.ambientLight=new Color(.48f,.59f,.7f);RenderSettings.ambientMode=UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.fog=true;RenderSettings.fogMode=FogMode.ExponentialSquared;RenderSettings.fogColor=new Color(.38f,.55f,.65f);RenderSettings.fogDensity=.000026f;
            var sun=new GameObject("Sun").AddComponent<Light>();sun.type=LightType.Directional;sun.intensity=2;sun.transform.rotation=Quaternion.Euler(35,-35,0);
            view=new GameObject("Chase Camera").AddComponent<Camera>();view.clearFlags=CameraClearFlags.SolidColor;view.backgroundColor=new Color(.32f,.53f,.7f);
            view.nearClipPlane=.3f;view.farClipPlane=50000;view.fieldOfView=60;view.gameObject.AddComponent<AudioListener>();
            Part(null,"Ocean",new Vector3(0,-20,0),new Vector3(60000,10,60000),Material(new Color(.035f,.18f,.24f)));
            var island=Material(new Color(.17f,.27f,.22f));
            for(int i=0;i<14;i++)Part(null,"Island "+i,new Vector3(Mathf.Sin(i*4.13f)*10000,-120,Mathf.Cos(i*2.1f)*10000),new Vector3(1600+i*120,400,2300),island,PrimitiveType.Sphere);
            var grid=Material(new Color(.12f,.3f,.34f));
            for(int i=-12;i<=12;i++) {
                Part(null,"North grid",new Vector3(i*1000,-13,0),new Vector3(2,1,24000),grid);
                Part(null,"East grid",new Vector3(0,-13,i*1000),new Vector3(24000,1,2),grid);
            }
            blue=Plane("BLUE / PLAYER",cyan);red=Plane("ORANGE / BANDIT",orange);
            blue.position=new Vector3(0,1828.8f,0);red.position=new Vector3(300,1828.8f,4200);
            view.transform.position=blue.position+new Vector3(0,10,-28);view.transform.LookAt(blue.position+Vector3.forward*25);
            pixel=new Texture2D(1,1);pixel.SetPixel(0,0,Color.white);pixel.Apply();
        }
        void OnDestroy(){
            stopping=true;
            if(worker!=null){try{if(!worker.HasExited){worker.StandardInput.Close();if(!worker.WaitForExit(800))worker.Kill();}worker.Dispose();}catch(Exception){} }
            if(Current==this)Current=null;
        }
    }
}
