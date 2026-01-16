#!/usr/bin/env python3
"""
检查后台生成任务状态的诊断工具
用于发现可能卡住或持续运行的任务
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 添加项目路径
sys.path.insert(0, '/Users/liguangyuan/Desktop/work/v1/content-creation-backend')

from src.models.tables.keyframe import Keyframe, KeyframeStatus
from src.models.tables.video_segment import VideoSegment, VideoStatus
from src.config.settings import settings


async def check_stale_tasks():
    """检查可能卡住的任务"""
    
    # 创建数据库连接
    engine = create_async_engine(
        settings.database_url,
        echo=False
    )
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as db:
        now = datetime.now(timezone.utc)
        
        print("=" * 80)
        print("🔍 后台任务状态检查")
        print("=" * 80)
        print(f"⏰ 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. 检查GENERATING状态的关键帧
        print("📊 检查关键帧生成任务...")
        print("-" * 80)
        
        result = await db.execute(
            select(Keyframe).where(
                Keyframe.status == KeyframeStatus.GENERATING
            ).order_by(Keyframe.updated_at.desc())
        )
        generating_keyframes = result.scalars().all()
        
        if generating_keyframes:
            print(f"⚠️  发现 {len(generating_keyframes)} 个正在生成的关键帧:")
            for kf in generating_keyframes:
                updated_at = kf.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                
                elapsed = now - updated_at
                elapsed_minutes = int(elapsed.total_seconds() / 60)
                
                status_icon = "🟢" if elapsed_minutes < 5 else "🟡" if elapsed_minutes < 30 else "🔴"
                
                print(f"  {status_icon} ID: {kf.id} | Script: {kf.script_id} | Segment: {kf.segment_id}")
                print(f"     更新时间: {updated_at.strftime('%Y-%m-%d %H:%M:%S')} ({elapsed_minutes}分钟前)")
                print(f"     提示词: {(kf.prompt or '')[:50]}...")
                
                if elapsed_minutes >= 120:  # 2小时
                    print(f"     ❌ 可能已卡住 (超过2小时)")
                elif elapsed_minutes >= 30:
                    print(f"     ⚠️  运行时间较长 (超过30分钟)")
                print()
        else:
            print("✅ 没有正在生成的关键帧")
            print()
        
        # 2. 检查PENDING状态的关键帧
        result = await db.execute(
            select(Keyframe).where(
                Keyframe.status == KeyframeStatus.PENDING
            ).order_by(Keyframe.created_at.desc())
        )
        pending_keyframes = result.scalars().all()
        
        if pending_keyframes:
            print(f"⏳ 发现 {len(pending_keyframes)} 个待生成的关键帧:")
            
            # 按脚本分组
            by_script = {}
            for kf in pending_keyframes:
                if kf.script_id not in by_script:
                    by_script[kf.script_id] = []
                by_script[kf.script_id].append(kf)
            
            for script_id, kfs in by_script.items():
                created_at = kfs[0].created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                elapsed = now - created_at
                elapsed_minutes = int(elapsed.total_seconds() / 60)
                
                print(f"  📝 Script {script_id}: {len(kfs)} 个待生成")
                print(f"     创建时间: {created_at.strftime('%Y-%m-%d %H:%M:%S')} ({elapsed_minutes}分钟前)")
                
                if elapsed_minutes >= 30:
                    print(f"     ⚠️  等待时间过长，可能后台任务未启动或已中断")
                print()
        else:
            print("✅ 没有待生成的关键帧")
            print()
        
        # 3. 检查GENERATING状态的视频
        print("📊 检查视频生成任务...")
        print("-" * 80)
        
        result = await db.execute(
            select(VideoSegment).where(
                VideoSegment.status == VideoStatus.GENERATING
            ).order_by(VideoSegment.updated_at.desc())
        )
        generating_videos = result.scalars().all()
        
        if generating_videos:
            print(f"⚠️  发现 {len(generating_videos)} 个正在生成的视频:")
            for video in generating_videos:
                updated_at = video.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                
                elapsed = now - updated_at
                elapsed_minutes = int(elapsed.total_seconds() / 60)
                
                status_icon = "🟢" if elapsed_minutes < 10 else "🟡" if elapsed_minutes < 60 else "🔴"
                
                print(f"  {status_icon} ID: {video.id} | Script: {video.script_id} | Segment Index: {video.segment_index}")
                print(f"     更新时间: {updated_at.strftime('%Y-%m-%d %H:%M:%S')} ({elapsed_minutes}分钟前)")
                print(f"     提示词: {(video.prompt or '')[:50]}...")
                
                if elapsed_minutes >= 120:  # 2小时
                    print(f"     ❌ 可能已卡住 (超过2小时)")
                elif elapsed_minutes >= 60:
                    print(f"     ⚠️  运行时间较长 (超过1小时)")
                print()
        else:
            print("✅ 没有正在生成的视频")
            print()
        
        # 4. 检查PENDING状态的视频
        result = await db.execute(
            select(VideoSegment).where(
                VideoSegment.status == VideoStatus.PENDING
            ).order_by(VideoSegment.created_at.desc())
        )
        pending_videos = result.scalars().all()
        
        if pending_videos:
            print(f"⏳ 发现 {len(pending_videos)} 个待生成的视频:")
            
            # 按脚本分组
            by_script = {}
            for video in pending_videos:
                if video.script_id not in by_script:
                    by_script[video.script_id] = []
                by_script[video.script_id].append(video)
            
            for script_id, videos in by_script.items():
                created_at = videos[0].created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                elapsed = now - created_at
                elapsed_minutes = int(elapsed.total_seconds() / 60)
                
                print(f"  📝 Script {script_id}: {len(videos)} 个待生成")
                print(f"     创建时间: {created_at.strftime('%Y-%m-%d %H:%M:%S')} ({elapsed_minutes}分钟前)")
                
                if elapsed_minutes >= 60:
                    print(f"     ⚠️  等待时间过长，可能后台任务未启动或已中断")
                print()
        else:
            print("✅ 没有待生成的视频")
            print()
        
        # 5. 统计总览
        print("=" * 80)
        print("📈 统计总览")
        print("=" * 80)
        
        # 关键帧统计
        result = await db.execute(select(Keyframe))
        all_keyframes = result.scalars().all()
        
        keyframe_stats = {
            "总数": len(all_keyframes),
            "GENERATING": len([k for k in all_keyframes if k.status == KeyframeStatus.GENERATING]),
            "PENDING": len([k for k in all_keyframes if k.status == KeyframeStatus.PENDING]),
            "COMPLETED": len([k for k in all_keyframes if k.status == KeyframeStatus.COMPLETED]),
            "FAILED": len([k for k in all_keyframes if k.status == KeyframeStatus.FAILED]),
        }
        
        print("关键帧:")
        for status, count in keyframe_stats.items():
            print(f"  {status}: {count}")
        print()
        
        # 视频统计
        result = await db.execute(select(VideoSegment))
        all_videos = result.scalars().all()
        
        video_stats = {
            "总数": len(all_videos),
            "GENERATING": len([v for v in all_videos if v.status == VideoStatus.GENERATING]),
            "PENDING": len([v for v in all_videos if v.status == VideoStatus.PENDING]),
            "COMPLETED": len([v for v in all_videos if v.status == VideoStatus.COMPLETED]),
            "FAILED": len([v for v in all_videos if v.status == VideoStatus.FAILED]),
        }
        
        print("视频:")
        for status, count in video_stats.items():
            print(f"  {status}: {count}")
        print()
        
        # 6. 建议
        print("=" * 80)
        print("💡 建议")
        print("=" * 80)
        
        has_issues = False
        
        if len(generating_keyframes) > 0:
            long_running = [kf for kf in generating_keyframes 
                          if (now - (kf.updated_at.replace(tzinfo=timezone.utc) if kf.updated_at.tzinfo is None else kf.updated_at)).total_seconds() > 7200]
            if long_running:
                print(f"⚠️  有 {len(long_running)} 个关键帧生成任务运行超过2小时，建议:")
                print("   1. 检查后端日志查看是否有错误")
                print("   2. 考虑将这些任务标记为失败并重新生成")
                has_issues = True
        
        if len(pending_keyframes) > 0:
            old_pending = [kf for kf in pending_keyframes 
                         if (now - (kf.created_at.replace(tzinfo=timezone.utc) if kf.created_at.tzinfo is None else kf.created_at)).total_seconds() > 1800]
            if old_pending:
                print(f"⚠️  有 {len(old_pending)} 个关键帧等待超过30分钟，建议:")
                print("   1. 检查后台任务是否正常运行")
                print("   2. 可能需要重启后端服务")
                has_issues = True
        
        if len(generating_videos) > 0:
            long_running = [v for v in generating_videos 
                          if (now - (v.updated_at.replace(tzinfo=timezone.utc) if v.updated_at.tzinfo is None else v.updated_at)).total_seconds() > 7200]
            if long_running:
                print(f"⚠️  有 {len(long_running)} 个视频生成任务运行超过2小时，建议:")
                print("   1. 检查后端日志查看是否有错误")
                print("   2. 考虑将这些任务标记为失败并重新生成")
                has_issues = True
        
        if len(pending_videos) > 0:
            old_pending = [v for v in pending_videos 
                         if (now - (v.created_at.replace(tzinfo=timezone.utc) if v.created_at.tzinfo is None else v.created_at)).total_seconds() > 3600]
            if old_pending:
                print(f"⚠️  有 {len(old_pending)} 个视频等待超过1小时，建议:")
                print("   1. 检查后台任务是否正常运行")
                print("   2. 可能需要重启后端服务")
                has_issues = True
        
        if not has_issues:
            print("✅ 所有任务状态正常")
        
        print()
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_stale_tasks())
