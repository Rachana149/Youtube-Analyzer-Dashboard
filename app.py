import streamlit as st
from googleapiclient.discovery import build
import pandas as pd
import numpy as np
import isodate
import warnings
import matplotlib.pyplot as plt


from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import tempfile


warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------- UI THEME ----------------
st.set_page_config(page_title="YouTube Analyzer", layout="wide")

st.markdown("""

<style>
.stApp {
    background: linear-gradient(135deg, #1a0000 0%, #8b0000 50%, #000000 100%);
    background-attachment: fixed;
}

h1, h2, h3, label {
    color: white !important;
    font-weight: 600;
}

section[data-testid="stSidebar"] {
    background: rgba(0,0,0,0.2);
    backdrop-filter: blur(6px);
}

.logo-container img {
    border-radius: 50%;
    width: 130px;
    height: 130px;
    object-fit: cover;
    border: 4px solid #ffffff;
    box-shadow: 0px 0px 18px rgba(255,255,255,0.7);
    transition: transform 0.3s ease-in-out, box-shadow 0.3s ease-in-out;
}

.logo-container img:hover {
    transform: scale(1.12);
    box-shadow: 0px 0px 35px rgba(255, 0, 0, 0.9);
    border-color: #ff0000;
}

div.stDownloadButton > button {
    background-color: #00c4ff;
    color: black;
    font-size: 16px;
    padding: 10px 20px;
    border-radius: 10px;
    font-weight: 600;
    transition: 0.3s;
}

div.stDownloadButton > button:hover {
    transform: scale(1.05);
    background-color: #73eaff;
}
</style>
""", unsafe_allow_html=True)





# ---------------- SESSION HANDLING ----------------
if "start_dashboard" not in st.session_state:
    st.session_state.start_dashboard = False

if "channel_url" not in st.session_state:
    st.session_state.channel_url = ""

# Load API Key from secrets.toml
st.session_state.api_key = st.secrets["API_KEY"]

logo_path = "Youtube_logo3.png"

# ---------------- HOME SCREEN ----------------
if not st.session_state.start_dashboard:

    col_left, col_right = st.columns([1.2, 1])
    with col_left:
        st.image(logo_path, width=520)

    with col_right:
        st.markdown("""
           <h1 style='font-size:55px;
            line-height:55px;
            text-align:center;
            color:white;
            text-shadow: 2px 2px 12px rgba(255,0,0,0.6);'>
            YouTube Analytics <br> Dashboard
            </h1>
        """, unsafe_allow_html=True)



        channel_url = st.text_input("📺 Enter YouTube Channel URL or ID")

        start_btn = st.button("🚀 Fetch Data")

        if start_btn:
            if not channel_url:
                st.error("⚠ Please enter a valid YouTube Channel URL.")
            else:
                st.session_state.channel_url = channel_url
                st.session_state.start_dashboard = True
                st.rerun()


# ---------------- FUNCTIONS ----------------
def extract_channel_id(url, youtube):
    url = url.strip()

    
    if "youtube.com/channel/" in url:
        return url.split("channel/")[1].split("/")[0]

   
    if "@" in url:
        handle = url.split("@")[1].split("/")[0]  
        try:
            res = youtube.channels().list(
                part="id",
                forHandle=handle
            ).execute()
            if res.get("items"):
                return res["items"][0]["id"]
        except Exception as e:
            st.error(f"Handle lookup failed: {e}")
            return None

    
    if url.startswith("UC") and len(url) > 20:
        return url

    return None



def get_uploads_playlist_id(channel_id, youtube):
    res = youtube.channels().list(
        part="contentDetails,snippet,statistics",
        id=channel_id
    ).execute()

    if not res.get("items"):
        return None, None, None, None

    info = res["items"][0]
    playlist_id = info["contentDetails"]["relatedPlaylists"]["uploads"]
    channel_name = info["snippet"]["title"]
    stats = info["statistics"]
    channel_logo = info["snippet"]["thumbnails"]["high"]["url"]

    return playlist_id, channel_name, stats, channel_logo


def get_videos_from_playlist(playlist_id, youtube, max_results=100):
    videos = []
    next_page = None

    while len(videos) < max_results:
        res = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page
        ).execute()

        for item in res.get("items", []):
            videos.append(item["contentDetails"]["videoId"])

        next_page = res.get("nextPageToken")
        if not next_page:
            break

    return videos

def get_video_stats(video_ids, youtube):
    data = []

    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        res = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(chunk)
        ).execute()

        for item in res["items"]:
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})

            view_count = int(stats.get("viewCount", 0))
            like_count = int(stats.get("likeCount", 0))
            comment_count = int(stats.get("commentCount", 0))

            engagement = round((like_count + comment_count) / view_count * 100, 3) if view_count > 0 else 0

            duration_iso = item["contentDetails"].get("duration", "PT0S")
            duration_minutes = round(isodate.parse_duration(duration_iso).total_seconds() / 60, 2)

            category_id = item["snippet"].get("categoryId", None)

            is_short = True if duration_minutes < 1 or "short" in snippet.get("title", "").lower() else False

            data.append({
                "VideoID": item["id"],
                "Title": snippet.get("title", ""),
                "CategoryID": category_id,
                "Type": "Short" if is_short else "Long",  
                "Published": snippet.get("publishedAt", "").split("T")[0],
                "Views": view_count,
                "Likes": like_count,
                "Comments": comment_count,
                "Engagement (%)": engagement,
                "Duration (mins)": duration_minutes,
                "URL": f"https://youtu.be/{item['id']}"
            })

    return data



    


# ---------------- DASHBOARD ----------------
if st.session_state.start_dashboard:

    youtube = build("youtube", "v3", developerKey=st.session_state.api_key)

    channel_id = extract_channel_id(st.session_state.channel_url, youtube)
    if not channel_id:
        st.error("❌ Invalid YouTube Channel URL.")
        st.stop()

    playlist_id, channel_name, stats, channel_logo = get_uploads_playlist_id(channel_id, youtube)
    
    col_logo, col_title = st.columns([1,5])

    with col_logo:
      st.markdown(f"<div class='logo-container'><img src='{channel_logo}'></div>", unsafe_allow_html=True)

    with col_title:
      st.title(f"{channel_name}")

    
    video_ids = get_videos_from_playlist(playlist_id, youtube, 120)
    df = pd.DataFrame(get_video_stats(video_ids, youtube))
    

    # ----- Add category mapping after dataframe creation -----

    CATEGORY_MAP = {
    "1": "Film & Animation", "2": "Autos & Vehicles", "10": "Music",
    "15": "Pets & Animals", "17": "Sports", "19": "Travel & Events",
    "20": "Gaming", "22": "People & Blogs", "23": "Comedy",
    "24": "Entertainment", "25": "News & Politics", "26": "How-to & Style",
    "27": "Education", "28": "Science & Tech", "29": "Nonprofits"
}

    df["Category"] = df["CategoryID"].astype(str).map(CATEGORY_MAP).fillna("Unknown")


    def generate_pdf(df, channel_name, total_views, subscribers, total_videos):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        pdf_path = temp_file.name
    
        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4

    # ------ Title ------
        c.setFont("Helvetica-Bold", 22)
        c.drawString(60, height - 50, "YouTube Analytics Report")

    # ------ Channel Name Section ------
        c.setFont("Helvetica-Bold", 14)
        c.drawString(60, height - 100, f"Channel: {channel_name}")

    # ------ KPI Section ------
        c.setFont("Helvetica", 12)
        c.drawString(60, height - 140, f"Total Videos: {total_videos}")
        c.drawString(60, height - 160, f"Total Views: {total_views:,}")
        c.drawString(60, height - 180, f"Subscribers: {subscribers}")

    # ------ Top Video ------
        top_title = df.sort_values(by="Views", ascending=False).iloc[0]["Title"]
        c.setFont("Helvetica-Bold", 12)
        c.drawString(60, height - 220, "Top Performing Video:")

        c.setFont("Helvetica", 11)
        c.drawString(60, height - 240, top_title[:70] + ("..." if len(top_title) > 70 else ""))

    # ------ Footer Branding ------
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(60, 30, "Generated via YouTube Analytics Dashboard")

        c.save()
        return pdf_path





    # ---- KPI ----
    total_videos = len(df)
    total_views = df["Views"].sum()
    subscribers = stats.get("subscriberCount", "Hidden")
    avg_views = int(df["Views"].mean()) if total_videos > 0 else 0
    avg_engagement = round(df["Engagement (%)"].mean(), 2)
    top_video = df.sort_values(by="Views", ascending=False).iloc[0]["Title"]


    def format_number(num):
        if isinstance(num, str) and num.lower() == "hidden":
            return "Hidden"
        num = float(num)
        return (
            f"{num/1_000_000_000:.1f}B" if num >= 1_000_000_000 else
            f"{num/1_000_000:.1f}M" if num >= 1_000_000 else
            f"{num/1_000:.1f}K" if num >= 1_000 else
            f"{int(num)}"
        )


    subscribers_display = format_number(subscribers)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric(" Total Videos", format_number(total_videos))
    k2.metric(" Total Views", format_number(total_views))
    k3.metric("Subscribers", subscribers_display)
    k4.metric(" Avg Views", format_number(avg_views))
    k5.metric(" Engagement", f"{avg_engagement}%")
    k6.metric(" Top Video", top_video)


    # -------- Tabs --------
    tab1, tab2, tab3, tab4, tab5,tab6 ,tab7,tab8,tab9 ,tab10= st.tabs([
        "📄 Video Table",
        "📈 Charts",
        "🏆 Top Videos",
        "🎬 Shorts vs Long Videos",
        "📈 Viral Score & Weekly Trend",
        "💰Revenue Insights ",
        "🧠 Insights Matrix",
        "🖼 Thumbnails",
        "⬇ Download",
        "🎯 Single Video Deep-Dive" 
         
        
    ])

    with tab1:
      st.dataframe(df, use_container_width=True)
      import altair as alt

    

    with tab2:
     st.subheader("📊 Performance Analysis Charts")

   
     import altair as alt

     df["Views_M"] = df["Views"] / 1_000_000  
     df["Likes_K"] = df["Likes"] / 1_000     

     st.subheader("Views vs Likes Trend")

     base = alt.Chart(df.reset_index()).encode(
     x=alt.X("index:Q", title="Video Number")
)

    
     views_line = base.mark_line(color="#00c3ff").encode(
    y=alt.Y("Views_M:Q", title="Views (Millions)"),
    tooltip=[
        alt.Tooltip("Title:N"),
        alt.Tooltip("Views_M:Q", title="Views (M)", format=".2f"),
        alt.Tooltip("Likes_K:Q", title="Likes (K)", format=".1f"),
    ]
)

    
     likes_line = base.mark_line(color="#ff4dd2").encode(
       y=alt.Y("Likes_K:Q", title="Likes (Thousands)", axis=alt.Axis(titleColor="#ff4dd2"))
)

     chart = alt.layer(views_line, likes_line).resolve_scale(
      y='independent'
).properties(height=350)

     st.altair_chart(chart, use_container_width=True)


     
     corr = round(df["Views"].corr(df["Likes"]), 2)
     top_video = df.iloc[df["Views"].idxmax()]["Title"]
     avg_views = df["Views_M"].mean()
     avg_likes = df["Likes_K"].mean()

     st.markdown(
    f"""
    💡 **Quick Insight:**

    -  Views & Likes relation: **`{corr}` correlation**
      → {"Strong engagement " if corr > 0.6 else "Weak engagement — content response varies "}

    -  Top performing video:  
      **“{top_video[:50]}...”**

    -  Average Metrics:  
       Avg Views: **{avg_views:.2f}M** | Avg Likes: **{avg_likes:.1f}K**
    """
)
     st.divider()

    
     
     category_colors = {
    "Music": "#A020F0",       
    "Trailer": "#2979FF",    
    "Shorts": "#FFD300",      
    "Entertainment": "#FF6D00", 
    "Unknown": "#9E9E9E"      
}

     df["Color"] = df["Category"].apply(lambda c: category_colors.get(c, "#9E9E9E"))



     st.subheader("Top 10 Most Viewed Videos")
     top10 = df.sort_values(by="Views", ascending=False).head(10).reset_index(drop=True)
     import altair as alt

     chart = alt.Chart(top10).mark_bar().encode(
       x=alt.X("Title:N", sort="-y", title="Video Title"),
       y=alt.Y("Views:Q", title="Views (Millions)", scale=alt.Scale(domain=[0, top10['Views'].max()])),
       color=alt.Color("Category:N", scale=alt.Scale(domain=list(category_colors.keys()),
                                                  range=list(category_colors.values())),
                    legend=alt.Legend(title="Content Type")),
     tooltip=[
        alt.Tooltip("Title:N"),
        alt.Tooltip("Views:Q", format=",.0f"),
        alt.Tooltip("Category:N")
    ]
).properties(height=400)

     st.altair_chart(chart, use_container_width=True)


     top_cat = top10.groupby("Category")["Views"].sum().idxmax()
     st.markdown(f"💡 **Insight:** Most top-performing videos belong to **`{top_cat}`** category — meaning audience strongly prefers this type of content.")



    
     st.write("⏳ Duration vs Views")
     scatter = alt.Chart(df).mark_circle(size=100,color="#0CBFFBFF" ).encode(
        x='Duration (mins):Q',
        y='Views:Q',
        tooltip=['Title', 'Views', 'Duration (mins)']
    ).interactive()
     st.altair_chart(scatter, use_container_width=True)

    
     optimal_len = df.loc[df["Views"].idxmax(), "Duration (mins)"]
     st.markdown(f" **Best performing video length:** Around **`{optimal_len} minutes`**.")

     st.divider()

    
     st.write("📅 Monthly Upload Trend")

   
     df["Published"] = pd.to_datetime(df["Published"], errors="coerce")
     df = df.dropna(subset=["Published"])
     df["Month"] = df["Published"].dt.to_period("M")


     monthly_uploads = df.groupby("Month")["VideoID"].count().reset_index()


     monthly_uploads["Month"] = monthly_uploads["Month"].astype(str)


     import altair as alt
     chart = alt.Chart(monthly_uploads).mark_bar(color="#E738E7FF").encode(
     x=alt.X("Month:N", title="Month"),  
     y=alt.Y("VideoID:Q", title="Uploads"),
     tooltip=[
        alt.Tooltip("Month:N", title="Month"),
        alt.Tooltip("VideoID:Q", title="Uploaded Videos"),
    ]
).properties(
      width="container",
      height=350,
     
)
     st.altair_chart(chart, use_container_width=True)


     most_active_month = monthly_uploads.loc[monthly_uploads["VideoID"].idxmax(), "Month"]
     st.markdown(f"📈 **Insight:** Most uploads were in **`{most_active_month}`** — more uploads = higher consistency! 📆🚀")
     st.divider()


    
     st.write("🎯 Most Popular Content Category")

     if "Category" in df.columns and not df["Category"].isna().all():

      category_views = df.groupby("Category")["Views"].sum().sort_values(ascending=False)

      if len(category_views) > 0:
          import matplotlib.pyplot as plt

          fig, ax = plt.subplots()
          ax.pie(category_views.values, labels=category_views.index, autopct="%1.1f%%")
          ax.axis("equal")  
          st.pyplot(fig)

       
          top_cat = category_views.idxmax()
          share = round((category_views.max() / category_views.sum()) * 100, 2)
          st.markdown(
            f"💡 **Insight:** `{top_cat}` category dominates with **{share}% views** — "
            f"audience clearly prefers this content."
        )

      else:
        st.warning("⚠ No category data available to plot.")

     else:
       st.warning("⚠ Category info not found.")


    with tab3:
        
        st.dataframe(df.sort_values(by="Views", ascending=False).head(5))

   
        st.subheader("🏆 Top Performing Videos")

    
        top5 = df.sort_values(by="Views", ascending=False).head(5)

    
        import altair as alt

        top_chart = alt.Chart(top5).mark_bar(color="#9670FF").encode(
         x=alt.X("Views:Q", title="Views"),
         y=alt.Y("Title:N", sort="-x", title="Video Title"),
         tooltip=[
            alt.Tooltip("Title:N", title="Video"),
            alt.Tooltip("Views:Q", title="Views", format=","),
            alt.Tooltip("Likes:Q", title="Likes", format=","),
            alt.Tooltip("URL:N", title="Video URL")
        ]
    ).properties(
         height=300,
         title="🔥 Top 5 Most Viewed Videos"
    )

        st.altair_chart(top_chart, use_container_width=True)

    
        st.write("📋 Detail View:")
        st.dataframe(top5[["Title", "Views", "Likes", "Engagement (%)", "URL"]], use_container_width=True)

    
        top_vid_title = top5.iloc[0]["Title"]
        top_ratio = round((top5.iloc[0]["Likes"] / top5.iloc[0]["Views"]) * 100, 2)

        st.markdown(
        f"""
        💡 **Insight:**  
        The video **"{top_vid_title[:50]}..."** is the top performer.  
        It not only has the highest views but also a strong engagement rate of **{top_ratio}%**, 
        indicating it resonated well with the audience.
        """
    )


    with tab9:
        st.subheader("📄 Export Analytics Report")

        if st.button("📥 Generate PDF Report"):
          pdf_path = generate_pdf(df, channel_name, total_views, subscribers, total_videos)

          with open(pdf_path, "rb") as f:
            st.download_button(
                label="⬇ Download PDF",
                data=f,
                file_name=f"{channel_name}_Analytics_Report.pdf",
                mime="application/pdf"
            )

        

          st.download_button("Download CSV", df.to_csv(index=False), "youtube_data.csv")

    with tab8:
        
        from PIL import Image, ImageStat
        import requests
        from io import BytesIO

        st.subheader("🎨 Thumbnail Brightness vs Views")

        def get_brightness(url):
         img = Image.open(BytesIO(requests.get(url).content)).convert("L")
         stat = ImageStat.Stat(img)
         return stat.mean[0]

        df["Thumbnail"] = df["VideoID"].apply(lambda x: f"https://i.ytimg.com/vi/{x}/hqdefault.jpg")
        df["Brightness"] = df["Thumbnail"].apply(get_brightness)

        chart = alt.Chart(df).mark_circle(size=90, color="#FF5722").encode(
        x=alt.X("Brightness:Q", title="Thumbnail Brightness (0–255)"),
        y=alt.Y("Views:Q", title="Views"),
        tooltip=["Title", "Brightness", "Views"]
).interactive()

        st.altair_chart(chart, use_container_width=True)

        best_brightness = int(df.loc[df["Views"].idxmax(), "Brightness"])
        st.markdown(f"💡 **Insight:** Best-performing thumbnail brightness ~ `{best_brightness}`.")

        st.subheader("🖼 Thumbnail Gallery")
        cols = st.columns(4)

        for i, row in df.iterrows():
            with cols[i % 4]:
                thumbnail = f"https://i.ytimg.com/vi/{row['VideoID']}/hqdefault.jpg"
                st.image(thumbnail, use_container_width=True)
                st.markdown(f"[▶️ {row['Title'][:40]}]({row['URL']})")
    


    with tab4:
      st.subheader("📊 Shorts vs Long Video Performance")

      shorts_data = df[df["Type"] == "Short"]
      long_data = df[df["Type"] == "Long"]

      colA, colB = st.columns(2)

      with colA:
         st.metric("📱 Shorts Count", len(shorts_data))
         st.metric("👁 Avg Views (Shorts)", f"{(shorts_data['Views'].mean()/1_000_000):.2f}M" if len(shorts_data) else "0")

      with colB:
         st.metric("📺 Long Videos Count", len(long_data))
         st.metric("👁 Avg Views (Long)", f"{(long_data['Views'].mean()/1_000_000):.2f}M" if len(long_data) else "0")

    
      compare_df = pd.DataFrame({
        "Type": ["Shorts", "Long Videos"],
        "Avg Views (M)": [
            shorts_data["Views"].mean() / 1_000_000 if len(shorts_data) else 0,
            long_data["Views"].mean() / 1_000_000 if len(long_data) else 0
        ]
    })

    
      import altair as alt

      chart = alt.Chart(compare_df).mark_bar(
        cornerRadiusTopLeft=10,
        cornerRadiusTopRight=10
    ).encode(
        x=alt.X("Type:N", title="Content Type"),
        y=alt.Y("Avg Views (M):Q", title="Average Views (Millions)", scale=alt.Scale(zero=True)),
        color=alt.Color("Type:N", scale=alt.Scale(
            domain=["Shorts", "Long Videos"],
            range=["#FFD300", "#4DA6FF"]  # Yellow for shorts, Blue for long
        )),
        tooltip=[
            alt.Tooltip("Type:N"),
            alt.Tooltip("Avg Views (M):Q", format=".2f", title="Avg Views (M)")
        ]
    ).properties(
        height=350,
        width=400,
        title="📊 Average Views Comparison"
    )

    
      st.altair_chart(chart, use_container_width=True)

   
      insight = (
        " **Shorts are performing better in terms of average views. **"
        if compare_df["Avg Views (M)"].iloc[0] > compare_df["Avg Views (M)"].iloc[1]
        else " **Long videos attract more average views — audience prefers detailed content. 🎬**"
    )

      st.markdown(insight)

    with tab5:
      st.subheader("🔥 Viral Score Analysis")

   
      df["Viral Score Raw"] = (
         df["Views"] * 0.60 +
         df["Likes"] * 0.30 +
         df["Comments"] * 0.10
    )

   
      df["Viral Score"] = np.round((df["Viral Score Raw"] / df["Viral Score Raw"].max()) * 100, 2)

    
      st.write("🏆 Top 10 Most Viral Videos")
      st.dataframe(df.sort_values(by="Viral Score", ascending=False)[["Title", "Views", "Likes", "Comments", "Viral Score"]].head(10))

    
      
      st.write("⚡ Viral Score Distribution — Top 10 Videos")

      top_viral = df.sort_values(by="Viral Score", ascending=False).head(10)

      st.bar_chart(
      top_viral.set_index("Title")["Viral Score"]
)

    
   
      st.subheader("📅 Weekly Upload & Performance Trend")

      df["Published"] = pd.to_datetime(df["Published"])
      df["Week"] = df["Published"].dt.to_period("W").astype(str)

      weekly_views = df.groupby("Week")["Views"].sum()

      st.line_chart(weekly_views)

    
      st.write("Insights")

      if weekly_views.iloc[-1] > weekly_views.iloc[-2]:
        st.success("📈 Recent week showing growth! Uploads are gaining momentum.")
      else:
        st.warning("📉 Recent week has fewer views — consistency or topic relevance may be dropping.")

    
      avg_viral = df["Viral Score"].mean()

      if avg_viral > 70:
        st.success(f"🔥 Channel is performing extremely well. Avg Viral Score: **{avg_viral:.2f}**")
      elif avg_viral > 50:
        st.info(f"👍 Stable performance. Avg Viral Score: **{avg_viral:.2f}** — Improve thumbnails or hooks for more reach.")
      else:
        st.warning(f"⚠ Average Viral Score Low: **{avg_viral:.2f}** — Optimize titles, content relevance, and audience retention.")

    #
    with tab6:
      st.subheader("💰 Revenue Insights & Monetization Strategy")

    # Sample RPM mapping (approx values by niche)
      RPM_MAP = {
        "Music": 0.60,
        "Entertainment": 1.20,
        "Comedy": 0.90,
        "Education": 2.50,
        "Technology": 3.20,
        "Science & Tech": 3.20,
        "How-to & Style": 1.80,
        "Gaming": 1.40,
        "News & Politics": 2.20,
        "People & Blogs": 1.00,
        "Unknown": 1.00
    }

    
      df["Estimated_RPM"] = df["Category"].map(RPM_MAP).fillna(1)
      df["Estimated_Revenue"] = (df["Views"] / 1000) * df["Estimated_RPM"]

      df_plot = df.copy()
      df_plot["Views_M"] = df_plot["Views"] / 1_000_000

      st.write("📊 Estimated Revenue vs Views")

    
      chart = alt.Chart(df_plot).mark_circle(size=120).encode(
        x=alt.X("Views_M:Q", title="Views (Millions)"),
        y=alt.Y("Estimated_Revenue:Q", title="Estimated Revenue (USD $)"),
        color=alt.Color("Category:N", legend=alt.Legend(title="Content Type")),
        tooltip=[
            alt.Tooltip("Title:N"),
            alt.Tooltip("Views_M:Q", title="Views (M)", format=".2f"),
            alt.Tooltip("Estimated_Revenue:Q", title="Estimated Revenue ($)", format=".2f"),
            alt.Tooltip("Category:N")
        ]
    ).properties(
        height=380,
        title="🎯 High Views vs High Revenue Potential"
    ).interactive()

      st.altair_chart(chart, use_container_width=True)

    # -------- Insight Section --------
      st.markdown("### Key Monetization Insights")

      top_rev = df.sort_values(by="Estimated_Revenue", ascending=False).iloc[0]
      low_rev = df.sort_values(by="Estimated_Revenue", ascending=True).iloc[0]
      avg_rev = df["Estimated_Revenue"].mean()

      st.markdown(
        f"""
         **Highest Revenue Video:**  
         `{top_rev['Title'][:45]}...` — Estimated **${top_rev['Estimated_Revenue']:.2f}**

         **Lowest Revenue Despite Views:**  
        `{low_rev['Title'][:45]}...` — Only **${low_rev['Estimated_Revenue']:.2f}**

        **Average Estimated Revenue Per Video:**  
        💵 **${avg_rev:.2f}**

        ---
        ### Interpretation  
        - High views ≠ High money — revenue depends on **content category & viewer geography**  
        - Educational / Tech categories generate **3x–6x more revenue per view**
        - Music & Entertainment gain **mass views but lower RPM**
        """
    )
      funnel = {
        "Total Videos": len(df),
        "Above Avg Views": len(df[df["Views"] > df["Views"].mean()]),
        "High Engagement (Views + Engagement > Avg)": len(df[(df["Views"] > df["Views"].mean()) & 
                                                            (df["Engagement (%)"] > df["Engagement (%)"].mean())]),
        "Viral Score > 80": len(df[df["Viral Score"] > 80])
    }

      funnel_df = pd.DataFrame(list(funnel.items()), columns=["Stage", "Video Count"])

    
      import plotly.express as px
      fig = px.funnel(
        funnel_df,
        x="Video Count",
        y="Stage",
        color="Stage",
        title="📊 Video Performance Funnel"
    )
      st.plotly_chart(fig, use_container_width=True)

      st.write("🔍 **Insights:**")
      total = funnel["Total Videos"]
      high_views = funnel["Above Avg Views"]
      high_engage = funnel["High Engagement (Views + Engagement > Avg)"]
      viral = funnel["Viral Score > 80"]

      st.markdown(f"""
    -  **{round((high_views/total)*100, 2)}% videos** got above-average views.
    -  **{round((high_engage/total)*100, 2)}% videos** performed well both""")
      

    with tab7:
     st.subheader("🧠 Correlation Insights Matrix")

     import seaborn as sns
     import matplotlib.pyplot as plt

     corr_columns = ["Views", "Likes", "Comments", "Engagement (%)", "Duration (mins)", "Viral Score"]
    
    
     corr_data = df[corr_columns].corr()

    
     fig, ax = plt.subplots(figsize=(8, 5))
     sns.heatmap(corr_data, annot=True, cmap="coolwarm", linewidths=0.5, fmt=".2f")
     st.pyplot(fig)

    
     highest_corr = corr_data.replace(1.0, 0).unstack().sort_values(ascending=False).index[0]
     metric1, metric2 = highest_corr

     st.markdown(f"""
    ###  Key Insight:
    The strongest relationship detected is between:

     **`{metric1}`** and **`{metric2}`**

    This means when `{metric1}` increases, `{metric2}` also shows a similar trend —  
    helping us understand what drives video success.
    """)

     st.info(" Use this insight to decide content strategy — जैसे अगर Likes & Views high correlate कर रहे हैं, तो बेहतर Call-to-Action, captions और thumbnails views बढ़ा सकते हैं।")

    with tab10:
       st.subheader("Single Video Deep-Dive")

       selected_title = st.selectbox(
        "Select a Video",
        df["Title"].tolist()
    )

       video = df[df["Title"] == selected_title].iloc[0]

       col1, col2, col3, col4 = st.columns(4)
       col1.metric(" Views", format_number(video["Views"]))
       col2.metric(" Likes", format_number(video["Likes"]))
       col3.metric(" Comments", format_number(video["Comments"]))
       col4.metric(" Engagement", f"{video['Engagement (%)']}%")

       st.markdown("### Video Details")
       st.write("**Title:**", video["Title"])
       st.write("**Category:**", video["Category"])
       st.write("**Duration:**", video["Duration (mins)"], "mins")
       st.write("**Published:**", video["Published"])
       st.write("**Type:**", video["Type"])
       st.write("**Video URL:**", video["URL"])

       thumbnail_url = f"https://i.ytimg.com/vi/{video['VideoID']}/hqdefault.jpg"
       st.image(thumbnail_url, caption="Video Thumbnail", width=350)

       st.markdown("###  Performance Insight")

       if video["Views"] > df["Views"].mean():
        st.success("This video performed ABOVE average.")
       else:
        st.warning("This video performed BELOW average.")

       if video["Engagement (%)"] > df["Engagement (%)"].mean():
        st.success("Engagement is strong.")
       else:
        st.info("ℹ Engagement can be improved with better CTA or title.")

    # ✅ ALWAYS SHOW COMPARISON
       st.markdown("###  Video vs Channel Average")

       compare_df = pd.DataFrame({
        "Metric": ["Views", "Likes", "Comments"],
        "This Video": [
            video["Views"],
            video["Likes"],
            video["Comments"]
        ],
        "Channel Average": [
            df["Views"].mean(),
            df["Likes"].mean(),
            df["Comments"].mean()
        ]
    })

       st.bar_chart(compare_df.set_index("Metric"))











    