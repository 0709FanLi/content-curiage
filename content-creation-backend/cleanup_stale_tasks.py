#!/usr/bin/env python3
"""
清理卡住的后台任务
将长时间运行的GENERATING任务标记为FAILED，并清理过期的PENDING任务
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# 添加项目路径
sys.path.insert(0, '/Users/liguangyuan/Desktop/work/v1/content-creation-backend')

from src.models.tables.keyframe import Keyframe, KeyframeStatus
from src.models.tables.video_segment import VideoSegment, VideoStatus
from src.config.settings import settings


async def cleanup_stale_tasks(
    keyframe_timeout_hours: int = 2,
    video_timeout_hours: int = 2,
    pending_timeout_hours: int = 1,
    dry_run: bool = True
):
    """
    清理卡住的任务
    
    Args:
        keyframe_timeout_hours: 关键帧GENERATING超时时间(小时)
        video_timeout_hours: 视频GENERATING超时时间(小时)
        pending_timeout_hours: PENDING状态超时时间(小时)
        dry_run: 是否为演练模式(不实际修改数据库)
    """
    
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
        print(f"🧹 清理卡住的后台任务 {'(演练模式)' if dry_run else '(执行模式)'}")
        print("=" * 80)
        print(f"⏰ 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⚙️  配置:")
        print(f"   - 关键帧GENERATING超时: {keyframe_timeout_hours}小时")
        print(f"   - 视频GENERATING超时: {video_timeout_hours}小时")
        print(f"   - PENDING超时: {pending_timeout_hours}小时")
        print()
        
        # 1. 清理卡住的关键帧GENERATING任务
        print("📊 处理关键帧GENERATING任务...")
        print("-" * 80)
        
        keyframe_timeout = timedelta(hours=keyframe_timeout_hours)
        cutoff_time = now - keyframe_timeout
        
        result = await db.execute(
            select(Keyframe).where(
                Keyframe.status == KeyframeStatus.GENERATING
            )
        )
        generating_keyframes = result.scalars().all()
        
        stale_keyframes = []
        for kf in generating_keyframes:
            updated_at = kf.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            
            if updated_at < cutoff_time:
                stale_keyframes.append(kf)
        
        if stale_keyframes:
            print(f"⚠️  发现 {len(stale_keyframes)} 个超时的关键帧:")
            for kf in stale_keyframes:
                updated_at = kf.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                
                elapsed = now - updated_at
                elapsed_hours = elapsed.total_seconds() / 3600
                
                print(f"  🔴 ID: {kf.id} | Script: {kf.script_id} | Segment: {kf.segment_id}")
                print(f"     更新时间: {updated_at.strftime('%Y-%m-%d %H:%M:%S')} ({elapsed_hours:.1f}小时前)")
                
                if not dry_run:
                    kf.status = KeyframeStatus.FAILED
                    kf.error_message = f"生成超时（超过{keyframe_timeout_hours}小时未更新），已自动清理"
            
            if not dry_run:
                await db.commit()
                print(f"✅ 已将 {len(stale_keyframes)} 个关键帧标记为FAILED")
            else:
                print(f"ℹ️  演练模式: 将标记 {len(stale_keyframes)} 个关键帧为FAILED")
        else:
            print("✅ 没有超时的关键帧GENERATING任务")
        print()
        
        # 2. 清理长时间等待的PENDING关键帧
        print("📊 处理关键帧PENDING任务...")
        print("-" * 80)
        
        pending_timeout = timedelta(hours=pending_timeout_hours)
        pending_cutoff_time = now - pending_timeout
        
        result = await db.execute(
            select(Keyframe).where(
                Keyframe.status == KeyframeStatus.PENDING
            )
        )
        pending_keyframes = result.scalars().all()
        
        stale_pending_keyframes = []
        for kf in pending_keyframes:
            created_at = kf.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            
            if created_at < pending_cutoff_time:
                stale_pending_keyframes.append(kf)
        
        if stale_pending_keyframes:
            print(f"⚠️  发现 {len(stale_pending_keyframes)} 个长时间等待的PENDING关键帧:")
            
            # 按脚本分组显示
            by_script = {}
            for kf in stale_pending_keyframes:
                if kf.script_id not in by_script:
                    by_script[kf.script_id] = []
                by_script[kf.script_id].append(kf)
            
            for script_id, kfs in by_script.items():
                created_at = kfs[0].created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                elapsed = now - created_at
                elapsed_hours = elapsed.total_seconds() / 3600
                
                print(f"  🟡 Script {script_id}: {len(kfs)} 个待生成")
                print(f"     创建时间: {created_at.strftime('%Y-%m-%d %H:%M:%S')} ({elapsed_hours:.1f}小时前)")
                
                if not dry_run:
                    for kf in kfs:
                        kf.status = KeyframeStatus.FAILED
                        kf.error_message = f"等待超时（创建后{pending_timeout_hours}小时未开始生成），已自动清理"
            
            if not dry_run:
                await db.commit()
                print(f"✅ 已将 {len(stale_pending_keyframes)} 个PENDING关键帧标记为FAILED")
            else:
                print(f"ℹ️  演练模式: 将标记 {len(stale_pending_keyframes)} 个PENDING关键帧为FAILED")
        else:
            print("✅ 没有长时间等待的PENDING关键帧")
        print()
        
        # 3. 清理卡住的视频GENERATING任务
        print("📊 处理视频GENERATING任务...")
        print("-" * 80)
        
        video_timeout = timedelta(hours=video_timeout_hours)
        video_cutoff_time = now - video_timeout
        
        result = await db.execute(
            select(VideoSegment).where(
                VideoSegment.status == VideoStatus.GENERATING
            )
        )
        generating_videos = result.scalars().all()
        
        stale_videos = []
        for video in generating_videos:
            updated_at = video.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            
            if updated_at < video_cutoff_time:
                stale_videos.append(video)
        
        if stale_videos:
            print(f"⚠️  发现 {len(stale_videos)} 个超时的视频:")
            for video in stale_videos:
                updated_at = video.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                
                elapsed = now - updated_at
                elapsed_hours = elapsed.total_seconds() / 3600
                
                print(f"  🔴 ID: {video.id} | Script: {video.script_id} | Segment Index: {video.segment_index}")
                print(f"     更新时间: {updated_at.strftime('%Y-%m-%d %H:%M:%S')} ({elapsed_hours:.1f}小时前)")
                
                if not dry_run:
                    video.status = VideoStatus.FAILED
                    video.error_message = f"生成超时（超过{video_timeout_hours}小时未更新），已自动清理"
            
            if not dry_run:
                await db.commit()
                print(f"✅ 已将 {len(stale_videos)} 个视频标记为FAILED")
            else:
                print(f"ℹ️  演练模式: 将标记 {len(stale_videos)} 个视频为FAILED")
        else:
            print("✅ 没有超时的视频GENERATING任务")
        print()
        
        # 4. 清理长时间等待的PENDING视频
        print("📊 处理视频PENDING任务...")
        print("-" * 80)
        
        result = await db.execute(
            select(VideoSegment).where(
                VideoSegment.status == VideoStatus.PENDING
            )
        )
        pending_videos = result.scalars().all()
        
        stale_pending_videos = []
        for video in pending_videos:
            created_at = video.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            
            if created_at < pending_cutoff_time:
                stale_pending_videos.append(video)
        
        if stale_pending_videos:
            print(f"⚠️  发现 {len(stale_pending_videos)} 个长时间等待的PENDING视频:")
            
            # 按脚本分组显示
            by_script = {}
            for video in stale_pending_videos:
                if video.script_id not in by_script:
                    by_script[video.script_id] = []
                by_script[video.script_id].append(video)
            
            for script_id, videos in by_script.items():
                created_at = videos[0].created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                
                elapsed = now - created_at
                elapsed_hours = elapsed.total_seconds() / 3600
                
                print(f"  🟡 Script {script_id}: {len(videos)} 个待生成")
                print(f"     创建时间: {created_at.strftime('%Y-%m-%d %H:%M:%S')} ({elapsed_hours:.1f}小时前)")
                
                if not dry_run:
                    for video in videos:
                        video.status = VideoStatus.FAILED
                        video.error_message = f"等待超时（创建后{pending_timeout_hours}小时未开始生成），已自动清理"
            
            if not dry_run:
                await db.commit()
                print(f"✅ 已将 {len(stale_pending_videos)} 个PENDING视频标记为FAILED")
            else:
                print(f"ℹ️  演练模式: 将标记 {len(stale_pending_videos)} 个PENDING视频为FAILED")
        else:
            print("✅ 没有长时间等待的PENDING视频")
        print()
        
        # 5. 总结
        print("=" * 80)
        print("📊 清理总结")
        print("=" * 80)
        
        total_cleaned = (
            len(stale_keyframes) + 
            len(stale_pending_keyframes) + 
            len(stale_videos) + 
            len(stale_pending_videos)
        )
        
        print(f"关键帧:")
        print(f"  - GENERATING超时: {len(stale_keyframes)} 个")
        print(f"  - PENDING超时: {len(stale_pending_keyframes)} 个")
        print(f"视频:")
        print(f"  - GENERATING超时: {len(stale_videos)} 个")
        print(f"  - PENDING超时: {len(stale_pending_videos)} 个")
        print()
        print(f"总计: {total_cleaned} 个任务")
        
        if dry_run:
            print()
            print("ℹ️  这是演练模式，没有实际修改数据库")
            print("💡 如需执行清理，请使用参数: --execute")
        else:
            print()
            print("✅ 清理完成！")
        print()
    
    await engine.dispose()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="清理卡住的后台任务")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行清理（默认为演练模式）"
    )
    parser.add_argument(
        "--keyframe-timeout",
        type=int,
        default=2,
        help="关键帧GENERATING超时时间(小时，默认2)"
    )
    parser.add_argument(
        "--video-timeout",
        type=int,
        default=2,
        help="视频GENERATING超时时间(小时，默认2)"
    )
    parser.add_argument(
        "--pending-timeout",
        type=int,
        default=1,
        help="PENDING状态超时时间(小时，默认1)"
    )
    
    args = parser.parse_args()
    
    asyncio.run(cleanup_stale_tasks(
        keyframe_timeout_hours=args.keyframe_timeout,
        video_timeout_hours=args.video_timeout,
        pending_timeout_hours=args.pending_timeout,
        dry_run=not args.execute
    ))
