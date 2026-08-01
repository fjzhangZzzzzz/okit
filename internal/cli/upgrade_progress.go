package cli

import (
	"fmt"
	"github.com/fjzhangZzzzzz/okit/internal/installation"
	"github.com/schollz/progressbar/v3"
	"io"
	"os"
	"time"
)

type terminalUpdateProgress struct {
	writer io.Writer
	stage  installation.ProgressStage
	bar    *progressbar.ProgressBar
	barMax int64
}

func (p *terminalUpdateProgress) ReportProgress(progress installation.Progress) {
	previousStage := p.stage
	switch progress.Stage {
	case installation.ProgressDownloadAsset, installation.ProgressDownloadChecksum:
		p.renderDownload(progress, previousStage)
	default:
		p.finishBar()
		_, _ = fmt.Fprintln(p.writer, updateProgressMessage(progress))
	}
	p.stage = progress.Stage
}
func (p *terminalUpdateProgress) renderDownload(progress installation.Progress, previousStage installation.ProgressStage) {
	if p.bar == nil || previousStage != progress.Stage {
		p.finishBar()
		p.newDownloadBar(progress)
	} else if p.barMax <= 0 && progress.Total > 0 {
		_ = p.bar.Clear()
		p.newDownloadBar(progress)
	}
	if p.bar != nil {
		_ = p.bar.Set64(progress.Current)
	}
}
func (p *terminalUpdateProgress) newDownloadBar(progress installation.Progress) {
	maximum := progress.Total
	if maximum <= 0 {
		maximum = -1
	}
	p.barMax = maximum
	p.bar = progressbar.NewOptions64(maximum, progressbar.OptionSetWriter(p.writer), progressbar.OptionSetDescription(updateProgressMessage(progress)), progressbar.OptionShowBytes(true), progressbar.OptionSetWidth(16), progressbar.OptionThrottle(65*time.Millisecond))
}
func (p *terminalUpdateProgress) finishBar() {
	if p.bar == nil {
		return
	}
	_ = p.bar.Finish()
	p.bar = nil
	p.barMax = 0
}
func updateProgressMessage(progress installation.Progress) string {
	switch progress.Stage {
	case installation.ProgressUpdateAvailable:
		return fmt.Sprintf("有可用更新：%s", progress.Version)
	case installation.ProgressDownloadAsset:
		return "正在下载更新"
	case installation.ProgressDownloadChecksum:
		return "正在下载校验和"
	case installation.ProgressVerifyChecksum:
		return "正在校验文件……"
	case installation.ProgressExtract:
		return "正在解压更新……"
	case installation.ProgressReplace:
		return "正在替换可执行文件……"
	case installation.ProgressComplete:
		if progress.Scheduled {
			return "已计划更新；当前进程退出后，新版本将生效。"
		}
		return "更新成功。"
	default:
		return "正在更新……"
	}
}
func isTerminal(writer io.Writer) bool {
	file, ok := writer.(*os.File)
	if !ok {
		return false
	}
	info, err := file.Stat()
	return err == nil && info.Mode()&os.ModeCharDevice != 0
}
