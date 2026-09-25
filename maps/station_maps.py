import geopandas as gpd, matplotlib.pyplot as plt, numpy as np
from shapely.geometry import Point, box
import matplotlib.patheffects as pe
plt.rcParams.update({'font.family':'serif','font.size':6.5,'axes.linewidth':0.5})

INK='#222222'; MUTED='#6b6b6b'; LAND='#f4f2ee'; CITY='#e3ded4'; URB='#cfc8bb'; WATER='#9cc3de'; ROAD='#b5aa98'; STATION='#c0392b'

ne_c=gpd.read_file('ne_10m_admin_0_countries.geojson')
roads=gpd.read_file('ne_10m_roads.geojson', bbox=(66,39,80,45))
riv=gpd.read_file('ne_10m_rivers_lake_centerlines.geojson', bbox=(66,39,80,45))
lakes=gpd.read_file('ne_10m_lakes.geojson', bbox=(66,39,80,45))
urb=gpd.read_file('ne_10m_urban_areas.geojson', bbox=(66,39,80,45))
kaz=gpd.read_file('gb_KAZ.geojson'); uzb=gpd.read_file('gb_UZB.geojson')
cities={
 'Almaty':  dict(poly=kaz[kaz.shapeName=='Almaty'], st=(76.9533,43.2341), epsg=32643, label='US Consulate General'),
 'Bishkek': dict(poly=gpd.read_file('bishkek_gb.geojson'), st=(74.5826,42.8278), epsg=32643, label='US Embassy'),
 'Tashkent':dict(poly=uzb[uzb.shapeName=='Tashkent'], st=(69.2719,41.3669), epsg=32642, label='US Embassy'),
}

def scalebar(ax, km, x0, y0):
    ax.plot([x0,x0+km*1000],[y0,y0],color=INK,lw=1.2,solid_capstyle='butt')
    ax.text(x0+km*500,y0+ (ax.get_ylim()[1]-ax.get_ylim()[0])*0.02,f'{km} km',ha='center',va='bottom',fontsize=5.5,color=INK)

def north(ax):
    ax.annotate('N',xy=(0.93,0.93),xytext=(0.93,0.80),xycoords='axes fraction',ha='center',va='center',fontsize=6,
                arrowprops=dict(arrowstyle='-|>',lw=0.6,color=INK),color=INK)

fig,axs=plt.subplots(1,4,figsize=(7.2,2.05),gridspec_kw=dict(width_ratios=[1.35,1,1,1]))
# overview
ax=axs[0]; ext=box(66,39,80.5,46)
cc=ne_c[ne_c.intersects(ext)].clip(ext)
cc.plot(ax=ax,color=LAND,edgecolor='#9a9384',lw=0.4)
for iso,nm,xy in [('KAZ','KAZAKHSTAN',(72.5,45.0)),('KGZ','KYRGYZSTAN',(74.5,41.4)),('UZB','UZBEKISTAN',(67.2,40.45)),('TJK','TAJIKISTAN',(69.3,39.4)),('CHN','CHINA',(78.8,40.4))]:
    ax.text(*xy,nm,fontsize=4.8,color=MUTED,ha='center',style='italic')
lakes.plot(ax=ax,color=WATER,lw=0)
for nm,d in cities.items():
    x,y=d['st']; ax.plot(x,y,'o',ms=3.6,mfc=STATION,mec='white',mew=0.6,zorder=5)
    off={'Almaty':(0.25,0.35),'Bishkek':(-0.2,0.4),'Tashkent':(-0.2,0.35)}[nm]
    ax.text(x+off[0],y+off[1],nm,fontsize=6,color=INK,ha='center',path_effects=[pe.withStroke(linewidth=1.5,foreground='white')])
ax.set_xlim(66,80.5); ax.set_ylim(39,46); ax.set_aspect(1/np.cos(np.radians(42.5)))
ax.tick_params(labelsize=5,length=2,width=0.4); ax.set_xticks([68,72,76,80]); ax.set_yticks([40,42,44,46])
ax.set_xticklabels([f'{v}°E' for v in [68,72,76,80]]); ax.set_yticklabels([f'{v}°N' for v in [40,42,44,46]])
ax.set_title('(a) Study area',fontsize=7,loc='left')

for ax,(nm,d),tag in zip(axs[1:],cities.items(),'bcd'):
    ep=d['epsg']; poly=d['poly'].to_crs(ep)
    cx,cy=poly.union_all().centroid.coords[0]
    minx,miny,maxx,maxy=poly.total_bounds; half=max(maxx-minx,maxy-miny)/2*1.18
    fr=gpd.GeoSeries([box(cx-half,cy-half,cx+half,cy+half)],crs=ep)
    frg=fr.to_crs(4326).iloc[0]
    ax.set_facecolor(LAND)
    u=urb[urb.intersects(frg)].to_crs(ep).clip(fr); u.plot(ax=ax,color=URB,lw=0)
    poly.plot(ax=ax,facecolor=CITY,edgecolor='none',alpha=0.55)
    l=lakes[lakes.intersects(frg)].to_crs(ep).clip(fr); 
    if len(l): l.plot(ax=ax,color=WATER,lw=0)
    r=riv[riv.intersects(frg)].to_crs(ep).clip(fr)
    if len(r): r.plot(ax=ax,color=WATER,lw=0.8)
    rd=roads[roads.intersects(frg)].to_crs(ep).clip(fr)
    if len(rd): rd.plot(ax=ax,color=ROAD,lw=0.6)
    poly.boundary.plot(ax=ax,color=INK,lw=0.8)
    st=gpd.GeoSeries([Point(d['st'])],crs=4326).to_crs(ep).iloc[0]
    ax.plot(st.x,st.y,marker='*',ms=9,mfc=STATION,mec='white',mew=0.7,zorder=6)
    ax.annotate(d['label'],(st.x,st.y),xytext=(0,-10),textcoords='offset points',ha='center',va='top',fontsize=5.5,color=INK,
                path_effects=[pe.withStroke(linewidth=1.6,foreground='white')])
    ax.set_xlim(cx-half,cx+half); ax.set_ylim(cy-half,cy+half); ax.set_aspect('equal')
    ax.set_xticks([]); ax.set_yticks([])
    km=10 if half>12000 else 5
    scalebar(ax,km,cx-half+0.07*2*half,cy-half+0.06*2*half); north(ax)
    ax.set_title(f'({tag}) {nm}',fontsize=7,loc='left')
    for s in ax.spines.values(): s.set_linewidth(0.5); s.set_color('#888')

# legend
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
h=[Line2D([],[],marker='*',ls='',ms=7,mfc=STATION,mec='white',label='PM$_{2.5}$ monitor'),
   Patch(facecolor=CITY,edgecolor=INK,lw=0.6,label='City boundary'),
   Patch(facecolor=URB,label='Built-up area'),
   Line2D([],[],color=ROAD,lw=0.8,label='Major roads'),
   Line2D([],[],color=WATER,lw=1,label='Rivers and lakes')]
fig.legend(handles=h,loc='lower center',ncol=5,frameon=False,fontsize=6,bbox_to_anchor=(0.5,-0.02))
plt.subplots_adjust(left=0.045,right=0.995,top=0.9,bottom=0.16,wspace=0.12)
fig.savefig('station_maps.png',dpi=400)
fig.savefig('station_maps.pdf')
