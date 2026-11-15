import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, appMode } from './api'
export type User={id:string;name:string;email:string;avatarUrl?:string}
type AuthValue={user:User|null;loading:boolean;mode:'demo'|'live';login:(email:string,password:string)=>Promise<void>;register:(name:string,email:string,password:string)=>Promise<void>;forgot:(email:string)=>Promise<void>;logout:()=>Promise<void>}
const Context=createContext<AuthValue|null>(null);const key='omniva.session.v1';const demo:User={id:'demo-learner',name:'Avery Morgan',email:'demo@omniva.ai'}
function read():User|null{try{return appMode==='demo'?JSON.parse(sessionStorage.getItem(key)||'null') as User|null:null}catch{return null}}
export function AuthProvider({children}:{children:ReactNode}){const[user,setUser]=useState<User|null>(read);const[loading,setLoading]=useState(appMode==='live');useEffect(()=>{if(appMode!=='live')return;let alive=true;api<{id?:string;name?:string;email?:string;user?:User}>('/auth/me').then(r=>{if(alive){const u=r.user??(r.id&&r.email?{id:r.id,name:r.name??'',email:r.email}:null);setUser(u)}}).catch(()=>{if(alive)setUser(null)}).finally(()=>{if(alive)setLoading(false)});return()=>{alive=false}},[])
 const value=useMemo<AuthValue>(()=>({user,loading,mode:appMode,
  async login(email,password){if(appMode==='demo'){if(email.toLowerCase()!=='demo@omniva.ai'||password!=='learn123')throw new Error('Use demo@omniva.ai and learn123 for the demo account.');sessionStorage.setItem(key,JSON.stringify(demo));setUser(demo);return}const result=await api<{user?:User;id?:string;name?:string;email?:string}>('/auth/login',{method:'POST',body:JSON.stringify({email,password})});const me=result?.user?result:await api<{user?:User;id?:string;name?:string;email?:string}>('/auth/me');const u=me.user??(me.id&&me.email?{id:me.id,name:me.name??'',email:me.email}:null);if(!u?.id||!u.email)throw new Error('The identity service returned an incomplete sign-in response.');setUser(u)},
  async register(name,email,password){if(appMode==='demo'){const u:User={id:`demo-${Date.now()}`,name,email};sessionStorage.setItem(key,JSON.stringify(u));setUser(u);return}await api('/auth/register',{method:'POST',body:JSON.stringify({name,email,password})})},
  async forgot(email){if(appMode==='demo')return;await api('/auth/password/forgot',{method:'POST',body:JSON.stringify({email})})},
  async logout(){if(appMode==='live')await api('/auth/logout',{method:'POST',body:'{}'});sessionStorage.removeItem(key);setUser(null)},
 }),[user,loading]);return <Context.Provider value={value}>{children}</Context.Provider>}
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(){const v=useContext(Context);if(!v)throw new Error('useAuth must be used inside AuthProvider');return v}
