#!/usr/bin/env python3
"""
安全版本的清理脚本
增加了额外的安全检查，降低误杀正在执行任务的风险
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


async def check_backend_running():
    """检查后端服务是否正在运行"""
    import subprocess
    try:
        result = subprocess.run(
            ['ps', 'aux'],
            capture_output=True,
            text=True
        )
        output = result.stdout
        
        # 检查是否有uvicorn进程
        is_running = 'uvicorn' in output and 'main:app' in output
        return is_running
    except Exception:
        return None  # 无法确定


async def analyze_task_safety(task, task_type='keyframe'):
    """
    分析任务是否安全清理
    
    返回：
    - (True, reason): 安全清理
    - (False, reason): 不安全，不应清理
    """
    now = datetime.now(timezone.utc)
    
    if task_type == 'keyframe':
        updated_at = task.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        
        elapsed_hours = (now - updated_at).total_seconds() / 3600
        
        # 安全阈值：6小时
        if elapsed_hours < 6:
            return (False, f"任务更新于{elapsed_hours:.1f}小时前，可能仍在执行")
        
        # 超过6小时，基本可以确定是卡住的
        return (True, f"任务更新于{elapsed_hours:.1f}小时前，确认卡住")
    
    elif task_type == 'pending':
        created_at = task.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        elapsed_hours = (now - created_at).total_seconds() / 3600
        
        # PENDING任务的安全阈值：3小时
        if elapsed_hours < 3:
            return (False, f"任务创建于{elapsed_hours:.1f}小时前，可能在排队")
        
        return (True, f"任务创建于{elapsed_hours:.1f}小时前，确认超时")
    
    return (False, "未知任务类型")


async def cleanup_stale_tasks_safe(
    interactive: bool = True,
    dry_run: bool = True
):
    """
    安全版本的清理任务
    
    Args:
        interactive: 是否交互式确认每个任务
        dry_run: 是否为演练模式
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
        print(f"🛡️  安全清理模式 {'(演练)' if dry_run else '(执行)'}")
        print("=" * 80)
        print(f"⏰ 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 检查后端服务状态
        print("🔍 检查后端服务状态...")
        backend_running = await check_backend_running()
        
        if backend_running is None:
            print("⚠️  无法确定后端服务状态")
        elif backend_running:
            print("✅ 后端服务正在运行")
            print("⚠️  警告: 后端运行时清理可能误杀正在执行的任务")
            print("💡 建议: 使用更保守的超时时间（6小时）")
        else:
            print("❌ 后端服务未运行")
            print("✅ 安全: 所有GENERATING任务都是遗留的")
        print()
        
        # 1. 分析GENERATING关键帧
        print("📊 分析GENERATING关键帧...")
        print("-" * 80)
        
        result = await db.execute(
            select(Keyframe).where(
                Keyframe.status == KeyframeStatus.GENERATING
            )
        )
        generating_keyframes = result.scalars().all()
        
        safe_to_clean = []
        not_safe = []
        
        for kf in generating_keyframes:
            is_safe, reason = await analyze_task_safety(kf, 'keyframe')
            
            if is_safe:
                safe_to_clean.append((kf, reason))
            else:
                not_safe.append((kf, reason))
        
        if safe_to_clean:
            print(f"✅ 发现 {len(safe_to_clean)} 个安全清理的任务:")
            for kf, reason in safe_to_clean:
                print(f"  🔴 ID: {kf.id} | Script: {kf.script_id} | {reason}")
        else:
            print("✅ 没有需要清理的GENERATING关键帧")
        
        if not_safe:
            print(f"\n⚠️  发现 {len(not_safe)} 个不建议清理的任务:")
            for kf, reason in not_safe:
                print(f"  🟡 ID: {kf.id} | Script: {kf.script_id} | {reason}")
        
        print()
        
        # 2. 分析PENDING关键帧
        print("📊 分析PENDING关键帧...")
        print("-" * 80)
        
        result = await db.execute(
            select(Keyframe).where(
                Keyframe.status == KeyframeStatus.PENDING
            )
        )
        pending_keyframes = result.scalars().all()
        
        safe_pending = []
        not_safe_pending = []
        
        for kf in pending_keyframes:
            is_safe, reason = await analyze_task_safety(kf, 'pending')
            
            if is_safe:
                safe_pending.append((kf, reason))
            else:
                not_safe_pending.append((kf, reason))
        
        if safe_pending:
            print(f"✅ 发现 {len(safe_pending)} 个安全清理的PENDING任务")
            # 按脚本分组
            by_script = {}
            for kf, reason in safe_pending:
                if kf.script_id not in by_script:
                    by_script[kf.script_id] = []
                by_script[kf.script_id].append(kf)
            
            for script_id, kfs in by_script.items():
                print(f"  🟡 Script {script_id}: {len(kfs)} 个")
        else:
            print("✅ 没有需要清理的PENDING关键帧")
        
        if not_safe_pending:
            print(f"\n⚠️  发现 {len(not_safe_pending)} 个不建议清理的PENDING任务")
        
        print()
        
        # 3. 执行清理
        total_to_clean = len(safe_to_clean) + len(safe_pending)
        
        if total_to_clean == 0:
            print("✅ 没有需要清理的任务")
            return
        
        print("=" * 80)
        print(f"📋 清理摘要:")
        print(f"  - GENERATING关键帧: {len(safe_to_clean)} 个")
        print(f"  - PENDING关键帧: {len(safe_pending)} 个")
        print(f"  - 总计: {total_to_clean} 个")
        print()
        
        if dry_run:
            print("ℹ️  演练模式: 不会实际修改数据库")
            print("💡 使用 --execute 参数执行实际清理")
        else:
            if interactive:
                response = input("确认清理这些任务? (yes/no): ")
                if response.lower() != 'yes':
                    print("❌ 清理已取消")
                    return
            
            # 清理GENERATING任务
            for kf, reason in safe_to_clean:
                kf.status = KeyframeStatus.FAILED
                kf.error_message = f"安全清理: {reason}"
            
            # 清理PENDING任务
            for kf, reason in safe_pending:
                kf.status = KeyframeStatus.FAILED
                kf.error_message = f"安全清理: {reason}"
            
            await db.commit()
            print(f"✅ 已清理 {total_to_clean} 个任务")
        
        print()
    
    await engine.dispose()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="安全清理卡住的后台任务")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="执行清理（默认为演练模式）"
    )
    parser.add_argument(
        "--no-interactive",
        action="store_true",
        help="非交互模式（不需要确认）"
    )
    
    args = parser.parse_args()
    
    asyncio.run(cleanup_stale_tasks_safe(
        interactive=not args.no_interactive,
        dry_run=not args.execute
    ))
