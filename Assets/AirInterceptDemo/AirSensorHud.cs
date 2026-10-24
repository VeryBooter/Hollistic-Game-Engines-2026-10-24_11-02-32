using System;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.EventSystems;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem.UI;
#endif

namespace AirIntercept {
    // Layout follows the supplied cockpit sketch. All displayed quantities use SI.
    public sealed class AirSensorHud : MonoBehaviour {
        AirInterceptDemo demo;
        Canvas canvas;
        Font font;
        Camera opticalCamera;
        RenderTexture opticalTexture;
        Text flight,air,status,track,echo,band,beam,eo,fuel,endurance,flow,airframe,warning;
        RectTransform sweep,blip,targetBox,eoMarker;
        Image[] fuelSegments;
        Text targetLabel;
        readonly Color ink=new Color(.025f,.06f,.08f,.88f);
        readonly Color green=new Color(.37f,1f,.71f);
        readonly Color red=new Color(1f,.38f,.28f);
        readonly Color dim=new Color(.28f,.51f,.49f);
        Transform Root {get{return canvas.transform;}}
        RectTransform Place(GameObject obj,float x,float y,float w,float h,Transform parent=null) {
            obj.layer=5;
            var rt=obj.GetComponent<RectTransform>();
            rt.SetParent(parent==null?Root:parent,false);rt.anchorMin=rt.anchorMax=new Vector2(0,1);rt.pivot=new Vector2(0,1);
            rt.anchoredPosition=new Vector2(x,-y);rt.sizeDelta=new Vector2(w,h);return rt;
        }
        Image Box(string name,float x,float y,float w,float h,Color color) {
            var obj=new GameObject(name,typeof(RectTransform),typeof(Image));Place(obj,x,y,w,h);
            var image=obj.GetComponent<Image>();image.color=color;image.raycastTarget=false;return image;
        }
        Text Label(string text,float x,float y,float w,float h,int size=14,Color? color=null) {
            var obj=new GameObject(text,typeof(RectTransform),typeof(Text));Place(obj,x,y,w,h);
            var t=obj.GetComponent<Text>();t.font=font;t.fontSize=size;t.color=color??green;t.text=text;
            t.horizontalOverflow=HorizontalWrapMode.Wrap;t.verticalOverflow=VerticalWrapMode.Truncate;t.raycastTarget=false;
            return t;
        }
        RectTransform Line(float x,float y,float dx,float dy,Color color,float thickness=1) {
            var image=Box("line",x,y,Mathf.Sqrt(dx*dx+dy*dy),thickness,color);
            var rt=image.rectTransform;rt.pivot=new Vector2(0,.5f);rt.localRotation=Quaternion.Euler(0,0,-Mathf.Atan2(dy,dx)*Mathf.Rad2Deg);return rt;
        }
        void Circle(float x,float y,float radius,Color color) {
            for(int i=0;i<72;i++){float a=i*Mathf.PI/36,b=(i+1)*Mathf.PI/36;Line(x+Mathf.Sin(a)*radius,y-Mathf.Cos(a)*radius,(Mathf.Sin(b)-Mathf.Sin(a))*radius,(-Mathf.Cos(b)+Mathf.Cos(a))*radius,color);}
        }
        void Panel(string heading,float x,float y,float w,float h) {
            Box(heading,x,y,w,h,ink);Line(x,y,w,0,green);Label(heading,x+12,y+8,w-24,22,12);
        }
        void Button(string text,float x,float y,float w,Action click) {
            var image=Box(text,x,y,w,26,new Color(.08f,.2f,.2f,.95f));image.raycastTarget=true;
            var button=image.gameObject.AddComponent<Button>();button.targetGraphic=image;button.onClick.AddListener(()=>click());
            var label=Label(text,x+5,y+5,w-10,20,11);label.alignment=TextAnchor.UpperCenter;
        }
        void Start() {
            demo=GetComponent<AirInterceptDemo>();font=Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            var obj=new GameObject("Sketch cockpit HUD",typeof(RectTransform),typeof(Canvas),typeof(CanvasScaler),typeof(GraphicRaycaster));
            canvas=obj.GetComponent<Canvas>();canvas.renderMode=RenderMode.ScreenSpaceCamera;canvas.worldCamera=demo.FlightCamera;
            canvas.planeDistance=2;canvas.sortingOrder=50;obj.layer=5;
            var scaler=obj.GetComponent<CanvasScaler>();scaler.uiScaleMode=CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution=new Vector2(1280,720);scaler.matchWidthOrHeight=.5f;
            if(EventSystem.current==null){var es=new GameObject("Demo input",typeof(EventSystem));
#if ENABLE_INPUT_SYSTEM
                es.AddComponent<InputSystemUIInputModule>().AssignDefaultActions();
#else
                es.AddComponent<StandaloneInputModule>();
#endif
            }
            BuildHud();BuildOptics();
        }
        void BuildHud() {
            Line(24,42,1232,0,green);Label("VECTOR / ELECTRO-OPTICAL INTERCEPT",30,14,700,26,18);
            status=Label("INITIALIZING",968,16,280,25,13);
            Panel("FLIGHT / SI",24,66,236,240);
            flight=Label("",38,104,210,132,18);
            air=Label("",38,240,210,50,12);
            Panel("PAYLOAD",24,320,236,67);Label("AAM --     GUN --\nNot fitted in this demo",38,350,210,34,12,dim);
            Panel("EM / RECEIVER",24,401,236,91);echo=Label("",38,432,215,54,12);
            Panel("FUEL / ENDURANCE",24,506,236,142);
            fuelSegments=new Image[48];
            for(int i=0;i<48;i++){
                float a=(i/48f*270+225)*Mathf.Deg2Rad;
                var line=Line(92+Mathf.Sin(a)*46,589-Mathf.Cos(a)*46,Mathf.Sin(a)*8,-Mathf.Cos(a)*8,green,3);
                fuelSegments[i]=line.GetComponent<Image>();
            }
            fuel=Label("",53,569,86,51,18);fuel.alignment=TextAnchor.MiddleCenter;
            endurance=Label("",151,554,100,43,16);flow=Label("",150,603,105,29,11);

            Panel("AESA / AUTOMATIC SCAN",956,66,300,333);
            const float cx=1106,cy=204,r=83;
            Circle(cx,cy,r,dim);Circle(cx,cy,r*.66f,dim);Circle(cx,cy,r*.33f,dim);
            Line(cx-r,cy,2*r,0,dim);Line(cx,cy-r,0,2*r,dim);
            foreach(float a in new[]{-Mathf.PI/3,Mathf.PI/3})Line(cx,cy,Mathf.Sin(a)*r,-Mathf.Cos(a)*r,green);
            Line(cx-5,cy+6,5,-13,green,2);Line(cx,cy-7,5,13,green,2);
            sweep=Line(cx,cy,0,-r,new Color(.7f,1,.35f),2);
            blip=Box("Radar contact",cx,cy,7,7,red).rectTransform;
            track=Label("",972,295,278,23,14);band=Label("",972,322,278,21,12);beam=Label("",972,345,278,20,11,dim);
            Button("1e9 Hz",970,369,86,()=>demo.SetFrequency(1e9));
            Button("1e10 Hz",1063,369,86,()=>demo.SetFrequency(1e10));
            Button("9.4e10 Hz",1156,369,86,()=>demo.SetFrequency(94e9));

            Panel("EO / VISIBLE LIGHT",956,413,300,192);
            eo=Label("",969,441,275,21,11);
            var video=new GameObject("Live EO image",typeof(RectTransform),typeof(RawImage));Place(video,969,464,274,127);
            opticalTexture=new RenderTexture(548,254,16);video.GetComponent<RawImage>().texture=opticalTexture;
            video.GetComponent<RawImage>().raycastTarget=false;
            Line(1098,527,16,0,green);Line(1106,519,0,16,green);
            eoMarker=Box("EO observed contact",0,0,16,16,new Color(0,0,0,0)).rectTransform;
            foreach(float edge in new[]{0f,15f}){
                var horizontal=Box("EO cue",0,edge,16,1,green);Place(horizontal.gameObject,0,edge,16,1,eoMarker);
                var vertical=Box("EO cue",edge,0,1,16,green);Place(vertical.gameObject,edge,0,1,16,eoMarker);
            }
            Label("5.50e-7 m / 0.08 m aperture",975,571,260,18,10);

            Panel("AIRFRAME / ASSIST",760,502,178,146);
            // Top view echoes the hand-drawn airframe diagram; no fabricated damage state.
            Line(810,543,0,70,green,3);Line(810,543,-11,21,green,2);Line(810,543,11,21,green,2);
            Line(810,564,-34,25,red,2);Line(776,589,34,-6,red,2);Line(810,564,34,25,red,2);Line(844,589,-34,-6,red,2);
            Line(810,601,-21,20,green,2);Line(789,621,21,-6,green,2);Line(810,601,21,20,green,2);Line(831,621,-21,-6,green,2);
            airframe=Label("",852,547,80,84,11);
            warning=Label("",390,85,500,40,21,red);warning.alignment=TextAnchor.MiddleCenter;
            targetBox=Box("Target cue",0,0,52,52,new Color(0,0,0,0)).rectTransform;
            foreach(float sx in new[]{0f,1f})foreach(float sy in new[]{0f,1f}){
                var part=new GameObject("corner",typeof(RectTransform),typeof(Image));
                Place(part,sx*50,sy*50,10,2,targetBox);part.GetComponent<Image>().color=red;part.GetComponent<Image>().raycastTarget=false;
                var vertical=new GameObject("corner",typeof(RectTransform),typeof(Image));Place(vertical,sx*50,sy*50,2,10,targetBox);vertical.GetComponent<Image>().color=red;vertical.GetComponent<Image>().raycastTarget=false;
            }
            targetLabel=Label("",0,0,220,23,13,red);
            Line(24,662,1232,0,green);
            Label("W/S altitude  A/D bank  Q/E rudder  SHIFT/CTRL thrust  TAB camera",30,674,900,23,13);
            Label("Ideal radar equation + EO geometry | no weather, clutter or terrain occlusion | SI quantities / linear SNR",30,699,980,18,10,dim);
            Button("PAUSE / P",1010,675,110,()=>demo.TogglePause());Button("RESET / R",1130,675,120,()=>demo.ResetFlight());
        }
        void BuildOptics() {
            foreach(var t in demo.PlayerTransform.GetComponentsInChildren<Transform>())t.gameObject.layer=31;
            opticalCamera=new GameObject("Visible EO sensor").AddComponent<Camera>();
            opticalCamera.targetTexture=opticalTexture;opticalCamera.fieldOfView=.36f*Mathf.Rad2Deg;
            opticalCamera.nearClipPlane=.2f;opticalCamera.farClipPlane=40000;
            opticalCamera.clearFlags=CameraClearFlags.SolidColor;opticalCamera.backgroundColor=demo.FlightCamera.backgroundColor;
            opticalCamera.cullingMask=~((1<<31)|(1<<5));
        }
        static string Sci(float x){return x.ToString("0.00e+0",System.Globalization.CultureInfo.InvariantCulture);}
        void LateUpdate() {
            if(demo==null)return;
            status.text=demo.Error!=null?"FLIGHT ERROR":demo.Latest==null?"INITIALIZING":!demo.TelemetryFresh?"TELEMETRY LOST":demo.Paused?"PAUSED":"JSBSim / SI / LIVE";
            if(demo.Latest==null){warning.text=demo.Error??"Initializing flight models";blip.gameObject.SetActive(false);targetBox.gameObject.SetActive(false);targetLabel.gameObject.SetActive(false);return;}
            var f=demo.Latest;var a=f.player;var r=f.player_sensor;
            flight.text="ALT   "+a.position[1].ToString("0")+" m\nTAS   "+a.speed_m_s.ToString("0.0")+" m/s\nHDG   "+a.yaw.ToString("0.000")+" rad\nMACH  "+a.mach.ToString("0.000")+"\nTHR   "+a.throttle.ToString("0.00");
            air.text=f.temperature_K.ToString("0.0")+" K\n"+f.pressure_Pa.ToString("0")+" Pa";
            echo.text="TX "+r.transmit_power_W.ToString("0")+" W\nRX "+Sci(r.received_power_W)+" W\nN  "+Sci(r.noise_power_W)+" W  SNR "+r.snr_linear.ToString("0.0");
            band.text=Sci(r.frequency_Hz)+" Hz / "+r.wavelength_m.ToString("0.00000")+" m";
            beam.text="BEAM "+r.beamwidth_rad.ToString("0.0000")+" rad / "+r.mode;
            track.text=r.detected?(r.illuminated?"TRACK ":"COAST ")+r.range_m.ToString("0")+" m / "+r.radial_velocity_m_s.ToString("0.0")+" m/s":"SEARCH / NO VALID TRACK";
            sweep.localRotation=Quaternion.Euler(0,0,90-r.beam_azimuth_rad*Mathf.Rad2Deg);
            blip.gameObject.SetActive(r.detected);
            if(r.detected){float d=Mathf.Min(1,r.range_m/20000)*83;blip.anchoredPosition=new Vector2(1106+Mathf.Sin(r.bearing_rad)*d,-204+Mathf.Cos(r.bearing_rad)*d);}
            eo.text=(f.player_eo.detected?"CONTACT / EO CUE":"SEARCH / VISIBLE CAMERA")+" / FOV "+f.player_eo.field_of_view_rad.ToString("0.00")+" rad";
            opticalCamera.transform.SetPositionAndRotation(demo.PlayerTransform.position+demo.PlayerTransform.forward*8+demo.PlayerTransform.up, demo.PlayerTransform.rotation);
            Vector3 opticalPoint=opticalCamera.WorldToViewportPoint(demo.OpponentTransform.position);
            eoMarker.gameObject.SetActive(f.player_eo.detected&&opticalPoint.z>0&&opticalPoint.x>0&&opticalPoint.x<1&&opticalPoint.y>0&&opticalPoint.y<1);
            eoMarker.anchoredPosition=new Vector2(969+opticalPoint.x*274-8,-464-(1-opticalPoint.y)*127+8);
            fuel.text=a.fuel_kg.ToString("0")+"\nkg";
            float seconds=a.fuel_flow_kg_s>1e-6?a.fuel_kg/a.fuel_flow_kg_s:0;
            endurance.text=seconds>0?seconds.ToString("0")+" s\nESTIMATE":"-- s";
            flow.text=a.fuel_flow_kg_s.ToString("0.00")+" kg/s";
            for(int i=0;i<fuelSegments.Length;i++)fuelSegments[i].color=i/(float)fuelSegments.Length<a.fuel_kg/Mathf.Max(1,a.initial_fuel_kg)?green:dim;
            airframe.text="BANK\n"+a.roll.ToString("0.00")+" rad\nPITCH\n"+a.pitch.ToString("0.00")+" rad";
            warning.text=f.crashed?"AIRCRAFT LOST / RESET":f.opponent_sensor.detected?"OPPONENT RADAR TRACK":"";
            Vector3 observedPosition=demo.OpponentTransform.position;
            if(!f.player_eo.detected && r.detected && r.track_position_m!=null)
                observedPosition=new Vector3(r.track_position_m[0],r.track_position_m[1],r.track_position_m[2]);
            Vector3 projected=demo.FlightCamera.WorldToViewportPoint(observedPosition);
            bool show=(r.detected||f.player_eo.detected)&&projected.z>0&&projected.x>.22f&&projected.x<.73f&&projected.y>.1f&&projected.y<.9f;
            targetBox.gameObject.SetActive(show);targetLabel.gameObject.SetActive(show);
            if(show){float x=projected.x*1280,y=(1-projected.y)*720;targetBox.anchoredPosition=new Vector2(x-26,-y+26);targetLabel.rectTransform.anchoredPosition=new Vector2(x+36,-y+8);targetLabel.text=r.detected?"RADAR / "+r.range_m.ToString("0")+" m":"EO / VISUAL CONTACT";}
        }
        void OnDestroy(){if(opticalCamera!=null)Destroy(opticalCamera.gameObject);if(opticalTexture!=null){opticalTexture.Release();Destroy(opticalTexture);}if(canvas!=null)Destroy(canvas.gameObject);}
    }
}
