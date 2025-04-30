package com.xiaohongshu.redcopilot.server.llmcq.service;

import java.util.Date;

import javax.annotation.Resource;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;

import com.alibaba.fastjson.JSONArray;
import com.alibaba.fastjson.JSONObject;
import com.google.common.collect.Lists;
import com.xiaohongshu.infra.utils.ObjectMapperUtils;
import com.xiaohongshu.redcopilot.common.dto.evaluation.EvaluationRequestDTO;
import com.xiaohongshu.redcopilot.common.dto.evaluation.EvaluationResponseDTO;
import com.xiaohongshu.redcopilot.common.dto.llmcq.StartAnalysisRequest;
import com.xiaohongshu.redcopilot.common.dto.llmcq.TestLLMRequest;
import com.xiaohongshu.redcopilot.server.llmcq.dto.LLMCqStartResp;
import com.xiaohongshu.redcopilot.server.llmcq.dto.Response;
import com.xiaohongshu.redcopilot.server.llmcq.dto.Result;
import com.xiaohongshu.redcopilot.server.llmcq.dto.ResultUtil;
import com.xiaohongshu.redcopilot.server.llmcq.enums.CodeAnalysisStatusEnum;
import com.xiaohongshu.redcopilot.server.llmcq.enums.ReturnCodeEnum;
import com.xiaohongshu.redcopilot.server.llmcq.mapper.CodeAnalysisRecordMapper;
import com.xiaohongshu.redcopilot.server.llmcq.po.CodeAnalysisRecord;

import lombok.extern.slf4j.Slf4j;

@Slf4j
@Service
public class LLMCqService {
    @Resource
    CodeAnalysisRecordMapper codeAnalysisRecordMapper;
    @Resource
    LLMCqAsyncService llmCqAsyncService;
    @Value("${domain.yunxiao}")
    String yunxiaoDomain;

    public Result startAnalysis(StartAnalysisRequest req) {
        String errorMsg = llmCqAsyncService.checkStartAnalysisRequest(req);
        if (errorMsg != null) {
            JSONObject data = new JSONObject();
            data.put("code", 300101);
            data.put("status", "FAILED");
            data.put("msg", errorMsg);
            return ResultUtil.error(-1, "fail", data);
        }

        // 1. 注册任务，返回execId
        CodeAnalysisRecord record = generateRecord(req);
        codeAnalysisRecordMapper.insert(record);
        Long execId = record.getId();
        log.info("startAnalysis execId: {}, req: {}", execId, ObjectMapperUtils.toJSON(req));

        // 2. 异步执行任务
        llmCqAsyncService.doCodeAnalysisAsynchronously(req, execId);

        LLMCqStartResp resp = new LLMCqStartResp();
        resp.setExecId(execId);
        return ResultUtil.success(resp);
    }


    public Result getAnalysisStatus(Long execId) {
        JSONObject data = new JSONObject();
        CodeAnalysisRecord record = codeAnalysisRecordMapper.selectById(execId);
        if (record == null) {
            data.put("code", 300101);
            data.put("status", "FAILED");
            data.put("msg", "execId not found");
            return ResultUtil.error(-1, "fail", data);
        }
        switch (CodeAnalysisStatusEnum.fromCode(record.getStatus())) {
            case RUNNING:
                data.put("code", 100100);
                data.put("status", "RUNNING");
                data.put("msg", "增量代码分析中...");
                return ResultUtil.success(data);
            case EXCEPTION:
                data.put("code", 300102);
                data.put("status", "FAILED");
                data.put("msg", "增量代码分析异常");
                data.put("reason", record.getErrorMessage());
                return ResultUtil.error(-1, "fail", data);
            case FAILED:
                data.put("code", 100100);
                data.put("status", "need_confirm");
                data.put("msg", "代码分析结果已生成，需要确认是否通过");
                data.put("webUrl", record.getYunxiaoLinkUrl());
                return ResultUtil.success(data);
            case PASSED:
            default:
                data.put("code", 100100);
                data.put("status", "Done");
                data.put("msg", "代码分析通过");
                data.put("webUrl", record.getYunxiaoLinkUrl());
                return ResultUtil.success(data);
        }
    }

    public Response getAnalysisReport(Long execId) {
        CodeAnalysisRecord record = codeAnalysisRecordMapper.selectById(execId);
        if (record == null) {
            return new Response<>(ReturnCodeEnum.ERROR_DATA, "not found", null);
        }
        switch (CodeAnalysisStatusEnum.fromCode(record.getStatus())) {
            case RUNNING:
                String msg = String.format("execId: %d is running, plz wait until task done.", execId);
                log.info(msg);
                return new Response<>(ReturnCodeEnum.ERROR_DATA, msg, null);
            case EXCEPTION:
                log.error(record.getErrorMessage());
                return new Response<>(ReturnCodeEnum.ERROR_SYSTEM_ERROR, record.getErrorMessage(), null);
            case FAILED:
            case PASSED:
            default:
                log.info("execId: {}, get analysis report done.", execId);
                JSONObject report = JSONObject.parseObject(record.getAnalysisResult());
                return Response.success(report);
        }
    }

    private CodeAnalysisRecord generateRecord(StartAnalysisRequest request) {
        String yunxiaoLinkUrl = getYunxiaoLinkUrl(request);
        return CodeAnalysisRecord.builder()
                .projectId(request.getProjectId())
                .repoUrl(request.getRepoUrl())
                .featureBranch(request.getFeatureBranch())
                .mainBranch(request.getMainBranch())
                .lanType(request.getLanType())
                .commitId(request.getCommitId())
                .yunxiaoLinkUrl(yunxiaoLinkUrl)
                .executor(request.getExecutor())
                .status(CodeAnalysisStatusEnum.RUNNING.getCode())
                .startTime(new Date())
                .build();
    }

    private String getYunxiaoLinkUrl(StartAnalysisRequest request) {
        String yunxiaoLinkUrl = yunxiaoDomain + "/ci/project";
        if (!StringUtils.isEmpty(request.getProjectId()) && !StringUtils.isEmpty(request.getPipelineInfoId())
                && !StringUtils.isEmpty(request.getPipelineId())) {
            String formatUrl = yunxiaoDomain + "/ci/project/%s/pipeline/%s/%s";
            yunxiaoLinkUrl = String.format(formatUrl, request.getProjectId(), request.getPipelineInfoId(), request.getPipelineId());
        }
        return yunxiaoLinkUrl;
    }


    public Response testLLM(TestLLMRequest req) {
        return Response.success(llmCqAsyncService.pureAnalysisFromString(req.getContent(), req.getProjectId()));
    }

    public EvaluationResponseDTO evaluation(EvaluationRequestDTO req) {
        EvaluationRequestDTO.EvaluateCode evaluateCode = req.getEvaluateCode();
        String code = evaluateCode.getCode();

        try {
            JSONObject jsonObject = llmCqAsyncService.callPaidModel(code, code, 1, req.getEvaluateCode().getRepoId(), req);
            JSONArray suggestions = jsonObject.getJSONArray("suggestions");
            if (suggestions == null) {
                log.error("evaluation error, suggestions is null");
                return new EvaluationResponseDTO();
            }
            EvaluationResponseDTO response = new EvaluationResponseDTO();
            response.setDefectDetailList(Lists.newArrayList());
            for (int i = 0; i < suggestions.size(); i++) {
                JSONObject suggestion = suggestions.getJSONObject(i);
                EvaluationResponseDTO.DefectDetail defectDetail = new EvaluationResponseDTO.DefectDetail();
                defectDetail.setDefectType(suggestion.getString("risk_type"));
                defectDetail.setDefectDesc(suggestion.getString("suggestion"));
                defectDetail.setDefectRow(suggestion.getInteger("row"));
                response.getDefectDetailList().add(defectDetail);
            }
            return response;
        } catch (Exception e) {
            log.error("evaluation error", e);
        }
        return new EvaluationResponseDTO();
    }
}
