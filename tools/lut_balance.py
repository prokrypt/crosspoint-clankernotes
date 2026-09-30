#!/usr/bin/env python3
"""Net DC drive per LUT row for the freeink SDK display tables.

Usage: python3 tools/lut_balance.py <freeink-sdk checkout>
Output: <row>=<net>/<driven frames>f. Net counts VDH/VSH1 as +1 and VDL/VSL
as -1 per frame (x repeat). A balanced transition set has WW=KK=0 and
KW+WK=0; an absolute (direct-gray / complement-OLD) set has every row 0.
Values >= 1000 mean a VDHR/level-3 phase was used. Table names are those at
freeink-sdk cd6f5b8; update the names if the SDK renames them.
"""
import re,sys,os
FI=sys.argv[1]
L=FI+'/libs/display/FreeInkDisplay/src/lut/'
D=FI+'/libs/display/FreeInkDisplay/src/driver/'
def arr(path,name,nested=False):
    s=open(path).read()
    i=s.index(name); j=s.index('{',i)
    depth=0;k=j
    while True:
        if s[k]=='{':depth+=1
        elif s[k]=='}':
            depth-=1
            if depth==0:break
        k+=1
    body=s[j:k+1]
    body=re.sub(r'//[^\n]*','',body)
    if nested:
        rows=re.findall(r'\{([^{}]*)\}',body)
        return [[int(x,16) for x in re.findall(r'0x[0-9A-Fa-f]+',r)] for r in rows]
    return [int(x,16) for x in re.findall(r'0x[0-9A-Fa-f]+',body)]
# UltraChip 6-byte groups; stop at first group with RP==0 or all TP==0 (UC8179 p.44)
def uc(row,vcom=False,n=42):
    row=(row+[0]*n)[:n]; net=0;fr=0
    for g in range(0,n-5,6):
        lv=row[g];tp=row[g+1:g+5];rp=row[g+5]
        if rp==0 or sum(tp)==0: break
        s=0
        for p in range(4):
            l=(lv>>(6-2*p))&3
            if l==1:s+=tp[p]
            elif l==2:s-=tp[p]
            elif l==3 and not vcom and tp[p]: s+=1000*tp[p]  # VDHR flag
        net+=s*rp; fr+=sum(tp)*rp
    return net,fr
def ucset(rows,names=('VCOM','WW','KW','WK','KK')):
    v,_=uc(rows[0],True)
    out=[]
    for r,nm in zip(rows[1:],names[1:]):
        n,f=uc(r); out.append(f"{nm}={n-v:+d}/{f}f")
    return f"vcom={v:+d} "+' '.join(out)
# UC8279 7-byte groups [?,P1..P4,?,?], P=rail<<6|frames (per Uc8279X4Driver.cpp:141-151)
def u79(row,n):
    row=(row+[0]*n)[:n];net=0;fr=0
    for g in range(0,n-6,7):
        for i in range(1,5):
            r=row[g+i]>>6;f=row[g+i]&0x3F
            if r==1:net+=f
            elif r==2:net-=f
            elif r==3 and f: net+=1000*f
            fr+=f
    return net,fr
def u79set(rows,n):
    return ' '.join(f"{nm}={u79(r,n)[0]:+d}/{u79(r,n)[1]}f" for nm,r in zip(('VCOM','WW','KW','WK','KK'),rows))
# SSD1677: 5 LUTs x 10 groups, timing 10 x [TPA..TPD,RP], repeat=RP+1
def ssd(t):
    res=[]
    for lut in range(5):
        net=0;fr=0
        for g in range(10):
            lv=t[lut*10+g]; tp=t[50+5*g:50+5*g+4]; rp=t[50+5*g+4]+1
            for p in range(4):
                l=(lv>>(6-2*p))&3
                if l==1:net+=tp[p]*rp
                elif l==2:net-=tp[p]*rp
                elif l==3:net+=1000*tp[p]*rp
                if l: fr+=tp[p]*rp
        res.append(f"L{lut}={net:+d}/{fr}f")
    return ' '.join(res)
print('== SSD1677 (VSH1 +, VSL -; frames with drive)')
for nm in ['lut_grayscale[]','lut_grayscale_sticky','lut_factory_quality[]']:
    print(nm, ssd(arr(L+'Ssd1677Luts.h',nm)))
print('== UC8179 (driver-local)')
g=arr(D+'Uc8179Driver.cpp','kGrayLuts[5]',True)
dark=arr(D+'Uc8179Driver.cpp','kDarkGrayLut[GRAY_LUT_LEN]')
aa=[g[0],g[1],g[2],dark,g[4]]
print('AA kGrayLuts(+dark as R23):',ucset(aa))
pb=[r[1:] for r in arr(D+'Uc8179Driver.cpp','kGrayPreBwMid[5][43]',True)]
print('kGrayPreBwMid:',ucset(pb))
dg=arr(L+'UltraChipDirectGrayLuts.h','kUltraChipDirectGray[5][42]',True)
# rows: VCOM, black, light, dark, white
v,_=uc(dg[0],True)
print('DirectGray rows (VCOM,black,light,dark,white):',' '.join(f"{nm}={uc(r)[0]-v:+d}/{uc(r)[1]}f" for nm,r in zip(('black','light','dark','white'),dg[1:])),f"vcom={v:+d}")
print('== UC8253 X3')
for b in ['normal','half','fast','full','gc','aa_pre_bw_mid']:
    rows=[arr(L+'Uc8253X3Luts.h',f'lut_x3_{r}_{b}[]') for r in ('vcom','ww','bw','wb','bb')]
    print(b.ljust(14),ucset(rows,('VCOM','WW','BW(KW)','WB(WK)','BB')))
print('== UC8279 X3 (d)')
for nm,n,pref in [('kUc8279X3_BwGc[5][43]',42,1),('kUc8279X3_BwDu[5][43]',42,1),('kUc8279X3_XtfAa[5][49]',49,0),('kUc8279X3_Xth4[5][49]',49,0),('kUc8279X3_XtfPreBwMid[5][43]',42,1)]:
    rows=[r[pref:] for r in arr(L+'Uc8279X3Luts.h',nm,True)]
    print(nm.split('[')[0].ljust(24),u79set(rows,n))
print('== UC8279 X4 (driver-local)')
for nm in ['kXtfAa02[5]','kXtfAa68[5]']:
    rows=arr(D+'Uc8279X4Driver.cpp',nm,True)
    rows=[r[1:] for r in rows]
    print(nm.ljust(24),u79set(rows,49))
rows=[r[1:] for r in arr(D+'Uc8279X4Driver.cpp','kXtfPreBwMid[5][PREBW_LUT_LEN + 1]',True)]
print('kXtfPreBwMid'.ljust(24),u79set(rows,42))
print('== UC8279C A4')
rows=[arr(L+'Uc8279cA4Luts.h',f'A4_UC8279C_LUT_2{i}[') for i in range(5)]
print('A4 full',u79set(rows,49))
f=arr(L+'Uc8279cA4Luts.h','A4_UC8279C_FAST_LUT[')
print('A4 fast',u79set([f[i*49:i*49+42] for i in range(5)],42))
gl=arr(L+'Uc8279cA4Luts.h','A4_UC8279C_GRAY_LUT[')
print('A4 gray',u79set([gl[i*49:(i+1)*49] for i in range(5)],49))
