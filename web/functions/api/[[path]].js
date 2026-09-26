// AITele Pages Function: server-side MTDS API proxy with password-protected session.
// Production requires AI_TELECOM_API_KEY, DASHBOARD_PASSWORD and SESSION_SECRET.
const json=(value,status=200,headers={})=>new Response(JSON.stringify(value),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff",...headers}});
const enc=new TextEncoder();
const hex=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,"0")).join("");
async function mac(secret,value){const key=await crypto.subtle.importKey("raw",enc.encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);return hex(await crypto.subtle.sign("HMAC",key,enc.encode(value)))}
async function digest(x){return hex(await crypto.subtle.digest("SHA-256",enc.encode(x)))}
function eq(a,b){if(a.length!==b.length)return false;let diff=0;for(let i=0;i<a.length;i++)diff|=a.charCodeAt(i)^b.charCodeAt(i);return diff===0}
async function valid(request,env){
 const cookie=request.headers.get("cookie")?.split(";").map(s=>s.trim()).find(s=>s.startsWith("aitele_session="))?.slice(15);
 if(!cookie||!env.SESSION_SECRET)return false;
 const [expiry,sig]=cookie.split(".");if(!/^\d{13}$/.test(expiry||"")||Date.now()>Number(expiry)||!sig)return false;
 return eq(sig,await mac(env.SESSION_SECRET,expiry));
}
function permitted(path,method){
 if(path==="phone-numbers"&&method==="GET")return true;
 if(path==="usage"&&method==="GET")return true;
 if(["agents","calls","knowledge-bases"].includes(path)&&["GET","POST"].includes(method))return true;
 if(/^agents\/[a-zA-Z0-9_-]{1,100}$/.test(path)&&["GET","PATCH","DELETE"].includes(method))return true;
 if(/^calls\/[a-zA-Z0-9_-]{1,100}$/.test(path)&&["GET","DELETE"].includes(method))return true;
 if(/^calls\/[a-zA-Z0-9_-]{1,100}\/recording$/.test(path)&&method==="GET")return true;
 if(/^knowledge-bases\/[a-zA-Z0-9_-]{1,100}$/.test(path)&&["GET","PATCH","DELETE"].includes(method))return true;
 if(/^knowledge-bases\/[a-zA-Z0-9_-]{1,100}\/documents$/.test(path)&&["GET","POST"].includes(method))return true;
 if(/^knowledge-bases\/[a-zA-Z0-9_-]{1,100}\/documents\/[a-zA-Z0-9_-]{1,100}$/.test(path)&&["GET","PATCH","DELETE"].includes(method))return true;
 return false;
}
export async function onRequest({request,env,params}){
 const method=request.method.toUpperCase(),u=new URL(request.url),path=(params.path||[]).join("/");
 if(!env.DASHBOARD_PASSWORD||!env.SESSION_SECRET)return json({error:"Quản trị viên cần cấu hình DASHBOARD_PASSWORD và SESSION_SECRET trên Cloudflare."},503);
 if(method!=="GET"&&method!=="HEAD"&&request.headers.get("origin")!==u.origin)return json({error:"Yêu cầu không cùng nguồn."},403);
 if(path==="auth/login"&&method==="POST"){
   let b;try{b=await request.json()}catch{return json({error:"Dữ liệu không hợp lệ."},400)}
   const ok=eq(await digest(String(b.password||"")),await digest(env.DASHBOARD_PASSWORD));
   if(!ok)return json({error:"Mật khẩu không đúng."},401);
   const expiry=String(Date.now()+8*60*60*1000),sig=await mac(env.SESSION_SECRET,expiry);
   return json({ok:true},200,{"set-cookie":`aitele_session=${expiry}.${sig}; HttpOnly; Secure; SameSite=Strict; Path=/api; Max-Age=28800`});
 }
 if(path==="auth/logout"&&method==="POST")return json({ok:true},200,{"set-cookie":"aitele_session=; HttpOnly; Secure; SameSite=Strict; Path=/api; Max-Age=0"});
 if(path==="auth/status"&&method==="GET")return json({authenticated:await valid(request,env),configured:!!env.AI_TELECOM_API_KEY});
 if(!(await valid(request,env)))return json({error:"Phiên đăng nhập đã hết hạn."},401);
 if(!env.AI_TELECOM_API_KEY)return json({error:"Chưa cấu hình AI_TELECOM_API_KEY; không thể gửi cuộc gọi thật."},503);
 if(!path.startsWith("v1/"))return json({error:"Đường dẫn không được hỗ trợ."},404);
 const resource=path.slice(3);
 if(!permitted(resource,method))return json({error:"Thao tác không được hỗ trợ."},405);
 const size=Number(request.headers.get("content-length")||0);
 if(size>10*1024*1024)return json({error:"Giới hạn tệp 10 MB trên giao diện này."},413);
 const allowed=new URLSearchParams();
 for(const [k,v] of u.searchParams)if(["page","limit","status","outcome","to","agent_id","score_min","score_max","from","until"].includes(k))allowed.append(k,v);
 const upstream=new URL("https://telecom.mtds.vn/api/v1/"+resource);
 upstream.search=allowed.toString();
 const heads={"authorization":"Bearer "+env.AI_TELECOM_API_KEY,"accept":"application/json"};
 if(["POST","PATCH"].includes(method))heads["content-type"]=request.headers.get("content-type")||"application/json";
 try{
  const response=await fetch(upstream,{method,headers:heads,body:["POST","PATCH"].includes(method)?request.body:undefined,redirect:"manual",signal:AbortSignal.timeout(30000)});
  if(response.status>=300&&response.status<400)return json({error:"Máy chủ API trả về chuyển hướng không mong đợi."},502);
  const contentType=response.headers.get("content-type")||"application/json";
  return new Response(response.body,{status:response.status,headers:{"content-type":contentType,"cache-control":"no-store","x-content-type-options":"nosniff"}});
 }catch{return json({error:"Không kết nối được API MTDS. Kiểm tra API key và trạng thái dịch vụ."},502)}
}
